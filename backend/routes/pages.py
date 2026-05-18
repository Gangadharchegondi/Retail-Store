"""
Page routes - Serve HTML templates
"""
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
import json

from fastapi import APIRouter, Request, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from backend.database import SessionLocal
from backend.models import AuditEvent, Order, OrderItem, Payment, User
from backend.session_auth import require_page_user
from backend.services.cart import clear_cart
from backend.services.audit import record_audit_event
from backend.services.cashfree import has_successful_cashfree_payment

router = APIRouter(tags=["pages"])

# Templates will be set by app initialization
templates: Jinja2Templates | None = None


def set_templates(tmpl: Jinja2Templates):
    """Set templates after app initialization."""
    global templates
    templates = tmpl


def _effective_order_status(order_status: str | None, payment_status: str | None) -> str:
    """Resolve a human-readable status from order/payment records."""
    paid_like = {"paid", "completed", "success", "succeeded"}
    pending_like = {"pending", "processing", "requires_payment_method"}
    failed_like = {"failed", "canceled", "cancelled", "expired"}

    order_key = str(order_status or "").strip().lower()
    payment_key = str(payment_status or "").strip().lower()

    if payment_key in paid_like or order_key in paid_like:
        return "Completed"
    if payment_key in failed_like or order_key in failed_like:
        return "Failed"
    if payment_key in pending_like or order_key in pending_like:
        return "Pending"

    fallback = payment_key or order_key
    return fallback.title() if fallback else "Pending"


def _is_admin_user(user_id: int) -> bool:
    """Simple admin gate based on bootstrap account id."""
    return int(user_id) == 1


def _orders_payload(
    db,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
    status: str = "all",
    q: str = "",
) -> dict:
    normalized_status = str(status or "all").strip().lower()
    normalized_query = str(q or "").strip()

    orders_query = db.query(Order).filter(Order.user_id == user_id)

    if normalized_status in {"completed", "paid", "success"}:
        orders_query = orders_query.filter(Order.status.in_(["paid", "completed", "success", "succeeded"]))
    elif normalized_status in {"pending", "processing"}:
        orders_query = orders_query.filter(Order.status.in_(["pending", "processing", "requires_payment_method"]))
    elif normalized_status in {"failed", "cancelled", "canceled", "expired"}:
        orders_query = orders_query.filter(Order.status.in_(["failed", "cancelled", "canceled", "expired"]))

    if normalized_query:
        if normalized_query.isdigit():
            orders_query = orders_query.filter(Order.id == int(normalized_query))
        else:
            orders_query = orders_query.filter(Order.payment_method.ilike(f"%{normalized_query}%"))

    total_orders = orders_query.count()
    total_pages = max(1, (total_orders + page_size - 1) // page_size)
    current_page = min(page, total_pages)

    orders = (
        orders_query
        .order_by(Order.created_at.desc())
        .offset((current_page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    order_ids = [order.id for order in orders]
    latest_payments: dict[int, Payment] = {}
    item_counts: dict[int, int] = {}

    if order_ids:
        payment_rows = (
            db.query(Payment)
            .filter(Payment.order_id.in_(order_ids))
            .order_by(Payment.order_id.asc(), Payment.id.desc())
            .all()
        )
        for payment in payment_rows:
            if payment.order_id not in latest_payments:
                latest_payments[payment.order_id] = payment

        item_rows = (
            db.query(OrderItem.order_id, OrderItem.quantity)
            .filter(OrderItem.order_id.in_(order_ids))
            .all()
        )
        for row_order_id, quantity in item_rows:
            item_counts[row_order_id] = item_counts.get(row_order_id, 0) + int(quantity or 0)

    order_rows = []
    for order in orders:
        payment = latest_payments.get(order.id)
        item_count = item_counts.get(order.id, 0)

        payment_method = "-"
        if payment and payment.method:
            payment_method = payment.method.upper()
        elif order.payment_method:
            payment_method = str(order.payment_method).upper()

        payment_status = "Pending"
        if payment and payment.status:
            payment_status = str(payment.status).title()
        elif order.status:
            payment_status = str(order.status).title()

        order_rows.append(
            {
                "id": order.id,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "created_at_display": order.created_at.strftime("%d %b %Y, %I:%M %p") if order.created_at else "-",
                "total_amount": round(float(order.total_amount or 0.0), 2),
                "item_count": item_count,
                "payment_method": payment_method,
                "payment_status": payment_status,
            }
        )

    return {
        "orders": order_rows,
        "filters": {
            "status": normalized_status,
            "q": normalized_query,
            "page_size": page_size,
        },
        "pagination": {
            "page": current_page,
            "page_size": page_size,
            "total_orders": total_orders,
            "total_pages": total_pages,
            "has_prev": current_page > 1,
            "has_next": current_page < total_pages,
            "prev_page": max(1, current_page - 1),
            "next_page": min(total_pages, current_page + 1),
        },
    }


def _audit_events_payload(
    db,
    actor_user_id: int,
    page: int = 1,
    page_size: int = 20,
    event_type: str = "all",
    q: str = "",
) -> dict:
    is_admin = _is_admin_user(actor_user_id)
    normalized_event_type = str(event_type or "all").strip().lower()
    normalized_query = str(q or "").strip()

    query = db.query(AuditEvent)
    if not is_admin:
        query = query.filter(AuditEvent.user_id == actor_user_id)

    if normalized_event_type != "all":
        query = query.filter(AuditEvent.event_type == normalized_event_type)

    if normalized_query:
        like = f"%{normalized_query}%"
        if normalized_query.isdigit():
            query = query.filter(AuditEvent.order_id == int(normalized_query))
        else:
            query = query.filter(
                AuditEvent.event_type.ilike(like)
                | AuditEvent.message.ilike(like)
            )

    total_events = query.count()
    total_pages = max(1, (total_events + page_size - 1) // page_size)
    current_page = min(page, total_pages)

    rows = (
        query
        .order_by(AuditEvent.created_at.desc())
        .offset((current_page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        metadata = None
        if row.metadata_json:
            try:
                metadata = json.loads(row.metadata_json)
            except Exception:
                metadata = {"raw": row.metadata_json}

        items.append(
            {
                "id": row.id,
                "user_id": row.user_id,
                "order_id": row.order_id,
                "event_type": row.event_type,
                "message": row.message,
                "metadata": metadata,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "created_at_display": row.created_at.strftime("%d %b %Y, %I:%M %p") if row.created_at else "-",
            }
        )

    return {
        "events": items,
        "is_admin": is_admin,
        "filters": {
            "event_type": normalized_event_type,
            "q": normalized_query,
            "page_size": page_size,
        },
        "pagination": {
            "page": current_page,
            "page_size": page_size,
            "total_events": total_events,
            "total_pages": total_pages,
            "has_prev": current_page > 1,
            "has_next": current_page < total_pages,
            "prev_page": max(1, current_page - 1),
            "next_page": min(total_pages, current_page + 1),
        },
    }


@router.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    """Serve login page."""
    return templates.TemplateResponse(request, "login.html")


@router.get("/login", response_class=HTMLResponse)
def login_page_alias(request: Request):
    """Serve login page from /login as well."""
    return templates.TemplateResponse(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Serve registration page."""
    return templates.TemplateResponse(request, "register.html")


@router.get("/site", response_class=HTMLResponse)
def site(request: Request):
    """Serve main shopping page."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    return templates.TemplateResponse(request, "index.html")


@router.get("/scan", response_class=HTMLResponse)
def scan_page(request: Request):
    """Serve live scanner page."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    return templates.TemplateResponse(request, "scan.html")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Serve dashboard page."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/admin/history", response_class=HTMLResponse)
def admin_history_page(request: Request):
    """Serve audit event history screen."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)
    return templates.TemplateResponse(
        request,
        "admin_history.html",
        {
            "request": request,
            "is_admin": _is_admin_user(user_id),
        },
    )


@router.get("/api/audit-events")
def audit_events_api(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=10, le=100),
    event_type: str = Query(default="all"),
    q: str = Query(default=""),
):
    """Return paginated audit history for admin or current user scope."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    user_id = int(guard)

    db = SessionLocal()
    try:
        return _audit_events_payload(
            db,
            actor_user_id=user_id,
            page=page,
            page_size=page_size,
            event_type=event_type,
            q=q,
        )
    finally:
        db.close()


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    """Serve profile page with user details and order summary."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)

    db = SessionLocal()
    try:
        profile_message = {
            "type": "success" if request.query_params.get("updated") == "1" else "error" if request.query_params.get("error") else None,
            "text": "Profile updated successfully." if request.query_params.get("updated") == "1" else "Unable to update profile. Username or email may already exist." if request.query_params.get("error") else "",
        }

        profile_user = db.query(User).filter(User.id == user_id).first()

        if not profile_user:
            return templates.TemplateResponse(
                request,
                "profile.html",
                {
                    "request": request,
                    "profile": None,
                    "stats": {
                        "total_orders": 0,
                        "paid_orders": 0,
                        "total_spent": 0.0,
                    },
                    "customer_details": {
                        "member_since": "-",
                        "last_order": "-",
                        "primary_payment": "-",
                        "loyalty_tier": "Starter",
                        "account_status": "Active",
                    },
                    "profile_message": profile_message,
                    "recent_orders": [],
                },
            )

        user_orders = (
            db.query(Order)
            .filter(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .all()
        )

        paid_orders = 0
        total_spent = 0.0
        recent_orders = []
        method_counter: Counter[str] = Counter()

        # Compute profile totals across the full order history.
        for order in user_orders:
            payment = (
                db.query(Payment)
                .filter(Payment.order_id == order.id)
                .order_by(Payment.id.desc())
                .first()
            )
            status = (payment.status if payment else order.status) or "pending"
            amount = round(float(order.total_amount or 0.0), 2)

            if str(status).lower() in {"paid", "completed"}:
                paid_orders += 1
                if payment and payment.amount is not None:
                    total_spent += round(float(payment.amount), 2)
                else:
                    total_spent += amount

            source_method = (payment.method if payment else order.payment_method) or ""
            normalized_method = str(source_method).strip().upper()
            if normalized_method and normalized_method != "-":
                method_counter[normalized_method] += 1

        member_since_dt = user_orders[-1].created_at if user_orders else None
        last_order_dt = user_orders[0].created_at if user_orders else None
        primary_payment = method_counter.most_common(1)[0][0] if method_counter else "-"

        if total_spent >= 10000:
            loyalty_tier = "Platinum"
        elif total_spent >= 5000:
            loyalty_tier = "Gold"
        elif total_spent >= 1000:
            loyalty_tier = "Silver"
        else:
            loyalty_tier = "Starter"

        # Show only the latest few orders in the profile table.
        for order in user_orders[:5]:
            payment = (
                db.query(Payment)
                .filter(Payment.order_id == order.id)
                .order_by(Payment.id.desc())
                .first()
            )
            status = (payment.status if payment else order.status) or "pending"
            method = (payment.method if payment else order.payment_method) or "-"
            amount = round(float(order.total_amount or 0.0), 2)

            recent_orders.append(
                {
                    "id": order.id,
                    "created_at": order.created_at,
                    "amount": amount,
                    "status": str(status).title(),
                    "method": str(method).upper(),
                }
            )

        return templates.TemplateResponse(
            request,
            "profile.html",
            {
                "request": request,
                "profile": {
                    "id": profile_user.id,
                    "username": profile_user.username,
                    "email": profile_user.email,
                },
                "stats": {
                    "total_orders": len(user_orders),
                    "paid_orders": paid_orders,
                    "total_spent": round(total_spent, 2),
                },
                "customer_details": {
                    "member_since": member_since_dt.strftime("%d %b %Y") if member_since_dt else "-",
                    "last_order": last_order_dt.strftime("%d %b %Y") if last_order_dt else "-",
                    "primary_payment": primary_payment,
                    "loyalty_tier": loyalty_tier,
                    "account_status": "Active",
                },
                "profile_message": profile_message,
                "recent_orders": recent_orders,
            },
        )
    finally:
        db.close()


@router.post("/profile/update")
def update_profile(request: Request, username: str = Form(...), email: str = Form(...)):
    """Update profile name and email for the current user."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)

    db = SessionLocal()
    try:
        current_user = db.query(User).filter(User.id == user_id).first()

        if not current_user:
            return RedirectResponse("/profile?error=notfound", status_code=303)

        username = (username or "").strip()
        email = (email or "").strip().lower()

        if not username or not email:
            return RedirectResponse("/profile?error=invalid", status_code=303)

        username_exists = (
            db.query(User)
            .filter(User.username == username, User.id != current_user.id)
            .first()
        )
        email_exists = (
            db.query(User)
            .filter(User.email == email, User.id != current_user.id)
            .first()
        )

        if username_exists or email_exists:
            return RedirectResponse("/profile?error=duplicate", status_code=303)

        current_user.username = username
        current_user.email = email
        db.commit()
        return RedirectResponse("/profile?updated=1", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse("/profile?error=save", status_code=303)
    finally:
        db.close()


@router.get("/orders", response_class=HTMLResponse)
def orders_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=50),
    status: str = Query(default="all"),
    q: str = Query(default=""),
):
    """Serve orders history page for the current user session."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    return templates.TemplateResponse(
        request,
        "orders.html",
        {
            "request": request,
            "filters": {
                "status": str(status or "all").strip().lower(),
                "q": str(q or "").strip(),
                "page_size": int(page_size),
                "page": int(page),
            },
        },
    )


@router.get("/api/orders/history")
def orders_history_api(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=50),
    status: str = Query(default="all"),
    q: str = Query(default=""),
):
    """Return deferred-hydration order history payload for current user."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    user_id = int(guard)

    db = SessionLocal()
    try:
        return _orders_payload(
            db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            status=status,
            q=q,
        )
    finally:
        db.close()


@router.post("/orders/delete")
def delete_order(request: Request, order_id: int = Form(...)):
    """Delete an order and its related payment/order-item rows."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return RedirectResponse("/orders", status_code=303)

        if order.user_id != user_id:
            return RedirectResponse("/orders", status_code=303)

        record_audit_event(
            db,
            event_type="order.deleted",
            message=f"Order #{order_id} deleted by user",
            user_id=user_id,
            order_id=order_id,
            metadata={
                "status": order.status,
                "payment_method": order.payment_method,
            },
        )
        db.query(Payment).filter(Payment.order_id == order_id).delete(synchronize_session=False)
        db.query(OrderItem).filter(OrderItem.order_id == order_id).delete(synchronize_session=False)
        db.query(Order).filter(Order.id == order_id).delete(synchronize_session=False)
        db.commit()
        return RedirectResponse("/orders", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse("/orders", status_code=303)
    finally:
        db.close()


@router.get("/payment", response_class=HTMLResponse)
def payment_page(request: Request):
    """Serve payment page."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    return templates.TemplateResponse(request, "payment.html")


@router.get("/payment-success", response_class=HTMLResponse)
def payment_success(request: Request, order_id: int | None = None, cf_order_id: str | None = None):
    """Serve payment success page."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)

    context = {
        "request": request,
        "order_id": "-",
        "invoice_no": "-",
        "invoice_date": "-",
        "customer_name": "SmartRetail Customer",
        "customer_email": "-",
        "item_count": 0,
        "amount": "0.00",
        "subtotal": "0.00",
        "tax": "0.00",
        "grand_total": "0.00",
        "payment_method": "-",
        "status": "Completed",
        "ordered_items": [],
        "bill_download_url": None,
    }

    if order_id is None:
        return templates.TemplateResponse(request, "success.html", context)

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
        if not order:
            return templates.TemplateResponse(request, "success.html", context)

        # Auto-verify Cashfree payment callback so status updates immediately.
        if cf_order_id:
            paid, payment_info = has_successful_cashfree_payment(cf_order_id)
            latest_payment = (
                db.query(Payment)
                .filter(Payment.order_id == order_id)
                .order_by(Payment.id.desc())
                .first()
            )

            if paid:
                callback_txn = str(payment_info.get("cf_payment_id") or cf_order_id)
                payment_already_completed = bool(
                    latest_payment and str(latest_payment.status or "").strip().lower() == "completed"
                )
                order_already_paid = str(order.status or "").strip().lower() in {"paid", "completed", "success", "succeeded"}
                callback_already_applied = bool(
                    latest_payment
                    and payment_already_completed
                    and order_already_paid
                    and str(latest_payment.transaction_id or "") == callback_txn
                )

                if not callback_already_applied:
                    if latest_payment:
                        latest_payment.status = "completed"
                        latest_payment.transaction_id = callback_txn
                    order.status = "paid"
                    record_audit_event(
                        db,
                        event_type="payment.cashfree.callback_verified",
                        message=f"Callback verified and marked paid for order #{order.id}",
                        user_id=user_id,
                        order_id=order.id,
                        metadata={
                            "cf_order_id": cf_order_id,
                            "cf_payment_id": payment_info.get("cf_payment_id"),
                            "idempotent_replay": False,
                        },
                    )
                    db.commit()
                clear_cart(user_id=user_id)
            else:
                callback_state = str((payment_info or {}).get("payment_status") or "").strip().upper()
                if callback_state in {"FAILED", "EXPIRED", "CANCELLED", "USER_DROPPED"}:
                    callback_already_failed = bool(
                        latest_payment and str(latest_payment.status or "").strip().lower() == "failed"
                    )
                    if not callback_already_failed:
                        if latest_payment:
                            latest_payment.status = "failed"
                            latest_payment.transaction_id = str((payment_info or {}).get("cf_payment_id") or cf_order_id)
                        order.status = "failed"
                        record_audit_event(
                            db,
                            event_type="payment.cashfree.callback_failed",
                            message=f"Callback marked failed for order #{order.id}",
                            user_id=user_id,
                            order_id=order.id,
                            metadata={
                                "cf_order_id": cf_order_id,
                                "payment_status": callback_state,
                            },
                        )
                        db.commit()

        order_user = None
        if order.user_id:
            order_user = db.query(User).filter(User.id == order.user_id).first()

        if not order_user:
            order_user = db.query(User).filter(User.id == user_id).first()

        payment = (
            db.query(Payment)
            .filter(Payment.order_id == order_id)
            .order_by(Payment.id.desc())
            .first()
        )

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order_id)
            .order_by(OrderItem.id.asc())
            .all()
        )

        ordered_items = [
            {
                "name": item.product_name,
                "quantity": item.quantity,
                "price": float(item.price),
                "total": round(float(item.price) * int(item.quantity), 2),
            }
            for item in items
        ]
        subtotal = round(sum(item["total"] for item in ordered_items), 2)
        tax = round(subtotal * 0.05, 2)
        grand_total = round(subtotal + tax, 2)

        method = "-"
        status = "Pending"
        if payment:
            method = (payment.method or "-").upper()
            status = _effective_order_status(order.status, payment.status)
        elif order.payment_method:
            method = order.payment_method.upper()
            status = _effective_order_status(order.status, None)

        context.update(
            {
                "order_id": order.id,
                "invoice_no": f"SR-{order.id:06d}",
                "invoice_date": order.created_at.strftime("%d %b %Y, %I:%M %p") if order.created_at else "-",
                "customer_name": (order_user.username if order_user and order_user.username else "SmartRetail Customer"),
                "customer_email": (order_user.email if order_user and order_user.email else "-"),
                "item_count": sum(int(item.quantity or 0) for item in items),
                "amount": f"{float(order.total_amount or 0.0):.2f}",
                "subtotal": f"{subtotal:.2f}",
                "tax": f"{tax:.2f}",
                "grand_total": f"{grand_total:.2f}",
                "payment_method": method,
                "status": status,
                "ordered_items": ordered_items,
                "bill_download_url": f"/payment-success/bill?order_id={order.id}&auto_print=1",
                "bill_pdf_url": f"/payment-success/bill.pdf?order_id={order.id}",
            }
        )

        return templates.TemplateResponse(request, "success.html", context)
    finally:
        db.close()


@router.get("/payment-success/bill", response_class=HTMLResponse)
def download_bill(request: Request, order_id: int, auto_print: int = 0):
    """Render a modern printable bill page for a completed order."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order_id)
            .order_by(OrderItem.id.asc())
            .all()
        )
        if not items:
            raise HTTPException(status_code=404, detail="No order items found")

        subtotal = round(sum(float(item.price) * int(item.quantity) for item in items), 2)
        tax = round(subtotal * 0.05, 2)
        grand_total = round(subtotal + tax, 2)
        latest_payment = (
            db.query(Payment)
            .filter(Payment.order_id == order_id)
            .order_by(Payment.id.desc())
            .first()
        )

        method = (
            (latest_payment.method if latest_payment and latest_payment.method else order.payment_method)
            or "-"
        ).upper()
        status = _effective_order_status(order.status, latest_payment.status if latest_payment else None)

        order_user = db.query(User).filter(User.id == order.user_id).first() if order.user_id else None
        ordered_items = [
            {
                "name": item.product_name,
                "quantity": int(item.quantity or 0),
                "price": float(item.price or 0.0),
                "total": round(float(item.price or 0.0) * int(item.quantity or 0), 2),
            }
            for item in items
        ]

        record_audit_event(
            db,
            event_type="invoice.html.generated",
            message=f"HTML bill generated for order #{order.id}",
            user_id=user_id,
            order_id=order.id,
            metadata={"invoice_no": f"SR-{order.id:06d}", "auto_print": bool(auto_print)},
        )
        db.commit()

        return templates.TemplateResponse(
            request,
            "bill.html",
            {
                "request": request,
                "order_id": order.id,
                "invoice_no": f"SR-{order.id:06d}",
                "invoice_date": order.created_at.strftime("%d %b %Y, %I:%M %p") if order.created_at else "-",
                "bill_generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "customer_name": order_user.username if order_user and order_user.username else "SmartRetail Customer",
                "customer_email": order_user.email if order_user and order_user.email else "-",
                "payment_method": method,
                "payment_reference": (latest_payment.transaction_id if latest_payment and latest_payment.transaction_id else "-"),
                "status": status,
                "item_count": sum(int(item.quantity or 0) for item in items),
                "ordered_items": ordered_items,
                "subtotal": f"{subtotal:.2f}",
                "tax": f"{tax:.2f}",
                "grand_total": f"{grand_total:.2f}",
                "auto_print": bool(auto_print),
                "bill_pdf_url": f"/payment-success/bill.pdf?order_id={order.id}",
            },
        )
    finally:
        db.close()


@router.get("/payment-success/bill.pdf")
def download_bill_pdf(request: Request, order_id: int):
    """Generate a downloadable PDF invoice for the selected order."""
    guard = require_page_user(request)
    if isinstance(guard, RedirectResponse):
        return guard
    user_id = int(guard)

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order_id)
            .order_by(OrderItem.id.asc())
            .all()
        )
        if not items:
            raise HTTPException(status_code=404, detail="No order items found")

        latest_payment = (
            db.query(Payment)
            .filter(Payment.order_id == order_id)
            .order_by(Payment.id.desc())
            .first()
        )
        status = _effective_order_status(order.status, latest_payment.status if latest_payment else None)
        method = (
            (latest_payment.method if latest_payment and latest_payment.method else order.payment_method)
            or "-"
        ).upper()

        subtotal = round(sum(float(item.price) * int(item.quantity) for item in items), 2)
        tax = round(subtotal * 0.05, 2)
        grand_total = round(subtotal + tax, 2)

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        page_width, page_height = A4

        cursor_y = page_height - 24 * mm
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(18 * mm, cursor_y, "SmartRetail Invoice")
        pdf.setFont("Helvetica", 10)
        cursor_y -= 7 * mm
        pdf.drawString(18 * mm, cursor_y, f"Invoice: SR-{order.id:06d}")
        pdf.drawString(85 * mm, cursor_y, f"Order: #{order.id}")
        pdf.drawString(140 * mm, cursor_y, f"Status: {status}")

        cursor_y -= 7 * mm
        pdf.drawString(18 * mm, cursor_y, f"Payment Method: {method}")
        payment_reference = latest_payment.transaction_id if latest_payment and latest_payment.transaction_id else "-"
        pdf.drawString(85 * mm, cursor_y, f"Reference: {payment_reference}")

        cursor_y -= 11 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(18 * mm, cursor_y, "Item")
        pdf.drawString(120 * mm, cursor_y, "Qty")
        pdf.drawRightString(150 * mm, cursor_y, "Unit")
        pdf.drawRightString(188 * mm, cursor_y, "Amount")
        cursor_y -= 3 * mm
        pdf.line(18 * mm, cursor_y, 190 * mm, cursor_y)
        cursor_y -= 5 * mm

        pdf.setFont("Helvetica", 10)
        for item in items:
            line_total = round(float(item.price or 0.0) * int(item.quantity or 0), 2)
            pdf.drawString(18 * mm, cursor_y, str(item.product_name or "Item"))
            pdf.drawString(120 * mm, cursor_y, str(int(item.quantity or 0)))
            pdf.drawRightString(150 * mm, cursor_y, f"INR {float(item.price or 0.0):.2f}")
            pdf.drawRightString(188 * mm, cursor_y, f"INR {line_total:.2f}")
            cursor_y -= 6 * mm
            if cursor_y < 34 * mm:
                pdf.showPage()
                cursor_y = page_height - 24 * mm
                pdf.setFont("Helvetica", 10)

        cursor_y -= 2 * mm
        pdf.line(120 * mm, cursor_y, 190 * mm, cursor_y)
        cursor_y -= 7 * mm
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(170 * mm, cursor_y, "Subtotal")
        pdf.drawRightString(188 * mm, cursor_y, f"INR {subtotal:.2f}")
        cursor_y -= 6 * mm
        pdf.drawRightString(170 * mm, cursor_y, "Tax (5%)")
        pdf.drawRightString(188 * mm, cursor_y, f"INR {tax:.2f}")
        cursor_y -= 7 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(170 * mm, cursor_y, "Grand Total")
        pdf.drawRightString(188 * mm, cursor_y, f"INR {grand_total:.2f}")

        cursor_y -= 10 * mm
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.drawString(18 * mm, cursor_y, "Generated by SmartRetail. Keep this invoice for accounting and returns.")

        pdf.save()
        buffer.seek(0)

        record_audit_event(
            db,
            event_type="invoice.pdf.generated",
            message=f"PDF bill generated for order #{order.id}",
            user_id=user_id,
            order_id=order.id,
            metadata={"invoice_no": f"SR-{order.id:06d}"},
        )
        db.commit()

        return Response(
            content=buffer.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="SmartRetail-Invoice-{order.id}.pdf"',
            },
        )
    finally:
        db.close()
