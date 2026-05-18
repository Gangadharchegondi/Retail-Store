"""Payment routes - Cashfree/COD checkout integration."""

import json
import threading
import time
from hashlib import sha1

from fastapi import APIRouter, Form, Request

from backend.database import SessionLocal
from backend.models import Order, OrderItem, Payment
from backend.services.cashfree import (
    CASHFREE_MODE,
    create_cashfree_order,
    get_cashfree_order,
    has_successful_cashfree_payment,
)
from backend.services.cart import get_cart_data
from backend.services.cart import clear_cart
from backend.services.payment import (
    gateway_checkout_minimum_inr,
    normalize_payment_method,
)
from backend.services.audit import record_audit_event
from backend.session_auth import require_api_user_id

router = APIRouter(prefix="/api/payment", tags=["payment"])

_CHECKOUT_CACHE_TTL_SECONDS = 45
_checkout_cache = {}
_checkout_cache_lock = threading.Lock()


def _cleanup_checkout_cache(now: float):
    expired_keys = [
        key for key, value in _checkout_cache.items()
        if (now - value.get("created_at", 0.0)) > _CHECKOUT_CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        _checkout_cache.pop(key, None)


def _cart_fingerprint(items, payment_method: str, upi_id: str = "", user_id: int | None = None) -> str:
    normalized_items = []
    for item in items:
        normalized_items.append({
            "name": str(item.get("name", "")).strip(),
            "category": str(item.get("category", "")).strip(),
            "price": round(float(item.get("price", 0.0)), 2),
            "qty": int(item.get("qty", 0)),
            "weight": round(float(item.get("weight", 0.0)), 3),
        })

    payload = {
        "user_id": int(user_id or 0),
        "payment_method": payment_method,
        "upi_id": (upi_id or "").strip().lower(),
        "items": sorted(normalized_items, key=lambda value: (value["name"], value["price"], value["qty"])),
    }
    return sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _sanitize_cart_items(items):
    sanitized = []
    for item in items:
        try:
            qty = int(item.get("qty", 0))
            price = round(float(item.get("price", 0.0)), 2)
            weight = round(float(item.get("weight", 0.0)), 3)
        except (TypeError, ValueError):
            continue

        if qty <= 0 or price <= 0:
            continue

        sanitized.append({
            "name": str(item.get("name", "Unknown")).strip() or "Unknown",
            "category": str(item.get("category", "General")).strip() or "General",
            "price": price,
            "qty": qty,
            "weight": max(0.0, weight),
        })

    return sanitized


def _calculate_totals(items):
    subtotal = round(sum(item["price"] * item["qty"] for item in items), 2)
    tax = round(subtotal * 0.05, 2)
    total_amount = round(subtotal + tax, 2)

    return {
        "subtotal": subtotal,
        "tax": tax,
        "total_amount": total_amount,
    }


def _create_checkout_from_cart(request: Request, payment_method: str = "card", upi_id: str = ""):
    user_id = require_api_user_id(request)
    db = SessionLocal()
    try:
        cart = get_cart_data(user_id=user_id)
        items = _sanitize_cart_items(cart.get("items", []))
        normalized_method = normalize_payment_method(payment_method)
        upi_id = (upi_id or "").strip()

        if not items:
            return {"error": "Cart is empty"}

        totals = _calculate_totals(items)
        total_amount = totals["total_amount"]
        base_url = str(request.base_url).rstrip("/")

        charge_amount = total_amount
        minimum_floor = gateway_checkout_minimum_inr(normalized_method)
        minimum_charge_applied = False
        minimum_adjustment = 0.0

        if normalized_method != "cash" and charge_amount < minimum_floor:
            minimum_adjustment = round(minimum_floor - charge_amount, 2)
            charge_amount = round(minimum_floor, 2)
            minimum_charge_applied = True

        if normalized_method == "cash":
            fingerprint = _cart_fingerprint(items, normalized_method, upi_id, user_id=user_id)
            now = time.time()

            with _checkout_cache_lock:
                _cleanup_checkout_cache(now)
                cached = _checkout_cache.get(fingerprint)

            if cached:
                return {
                    "checkout_url": cached["checkout_url"],
                    "order_id": cached["order_id"],
                    "minimum_charge_applied": False,
                    "minimum_adjustment": 0.0,
                    "total_amount": cached["total_amount"],
                    "payment_completed": True,
                    "reused_session": True,
                }

            order = Order(
                user_id=user_id,
                total_amount=charge_amount,
                status="paid",
                payment_method=normalized_method,
            )
            db.add(order)
            db.flush()

            for item in items:
                db.add(OrderItem(
                    order_id=order.id,
                    product_name=item["name"],
                    product_category=item["category"],
                    price=item["price"],
                    quantity=item["qty"],
                    weight=item["weight"],
                ))

            payment_record = Payment(
                order_id=order.id,
                amount=charge_amount,
                method=normalized_method,
                status="completed",
                transaction_id=f"cash-{order.id}",
            )
            payment_record.payment_data = json.dumps({
                "payment_method": normalized_method,
                "payment_type": "manual",
                "upi_id": upi_id,
                "cart_fingerprint": fingerprint,
                "subtotal": totals["subtotal"],
                "tax": totals["tax"],
                "total_amount": charge_amount,
                "minimum_charge_applied": minimum_charge_applied,
                "minimum_adjustment": minimum_adjustment,
            })
            db.add(payment_record)
            record_audit_event(
                db,
                event_type="order.cash.completed",
                message=f"Cash checkout completed for order #{order.id}",
                user_id=user_id,
                order_id=order.id,
                metadata={
                    "payment_method": normalized_method,
                    "amount": charge_amount,
                    "subtotal": totals["subtotal"],
                    "tax": totals["tax"],
                },
            )
            db.commit()
            clear_cart(user_id=user_id)

            checkout_url = f"{base_url}/payment-success?order_id={order.id}"

            with _checkout_cache_lock:
                _checkout_cache[fingerprint] = {
                    "checkout_url": checkout_url,
                    "order_id": order.id,
                    "minimum_charge_applied": minimum_charge_applied,
                    "minimum_adjustment": minimum_adjustment,
                    "total_amount": charge_amount,
                    "payment_completed": True,
                    "created_at": now,
                }

            return {
                "checkout_url": checkout_url,
                "order_id": order.id,
                "minimum_charge_applied": minimum_charge_applied,
                "minimum_adjustment": minimum_adjustment,
                "total_amount": charge_amount,
                "payment_completed": True,
                "reused_session": False,
            }

        order = Order(
            user_id=user_id,
            total_amount=charge_amount,
            status="pending",
            payment_method=normalized_method,
        )
        db.add(order)
        db.flush()

        for item in items:
            db.add(OrderItem(
                order_id=order.id,
                product_name=item["name"],
                product_category=item["category"],
                price=item["price"],
                quantity=item["qty"],
                weight=item["weight"],
            ))

        return_url = f"{base_url}/payment-success?order_id={order.id}&cf_order_id={{order_id}}"
        cashfree_order = create_cashfree_order(
            amount=charge_amount,
            order_id=order.id,
            return_url=return_url,
            payment_method=normalized_method,
        )

        if not cashfree_order:
            db.rollback()
            return {
                "error": "Failed to create Cashfree order",
            }

        payment_record = Payment(
            order_id=order.id,
            amount=charge_amount,
            method=normalized_method,
            status="pending",
            transaction_id=cashfree_order.get("cashfree_order_id"),
        )
        payment_record.payment_data = json.dumps({
            "provider": "cashfree",
            "cashfree_order_id": cashfree_order.get("cashfree_order_id"),
            "cf_order_id": cashfree_order.get("cf_order_id"),
            "payment_session_id": cashfree_order.get("payment_session_id"),
            "payment_link": cashfree_order.get("payment_link"),
            "payment_method": normalized_method,
            "minimum_charge_applied": minimum_charge_applied,
            "minimum_adjustment": minimum_adjustment,
            "subtotal": totals["subtotal"],
            "tax": totals["tax"],
            "total_amount": charge_amount,
        })
        db.add(payment_record)
        record_audit_event(
            db,
            event_type="order.online.initiated",
            message=f"Online checkout initiated for order #{order.id}",
            user_id=user_id,
            order_id=order.id,
            metadata={
                "provider": "cashfree",
                "payment_method": normalized_method,
                "amount": charge_amount,
                "cashfree_order_id": cashfree_order.get("cashfree_order_id"),
            },
        )
        db.commit()

        return {
            "payment_provider": "cashfree",
            "order_id": order.id,
            "minimum_charge_applied": minimum_charge_applied,
            "minimum_adjustment": minimum_adjustment,
            "total_amount": charge_amount,
            "cashfree": {
                "mode": CASHFREE_MODE,
                "order_id": cashfree_order.get("cashfree_order_id"),
                "cf_order_id": cashfree_order.get("cf_order_id"),
                "payment_session_id": cashfree_order.get("payment_session_id"),
                "payment_link": cashfree_order.get("payment_link"),
            },
        }
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()


@router.post("/checkout-from-cart")
def checkout_from_cart(
    request: Request,
    payment_method: str = Form(default="upi"),
    upi_id: str = Form(default=""),
):
    return _create_checkout_from_cart(request=request, payment_method=payment_method, upi_id=upi_id)


@router.post("/cashfree-checkout")
def create_cashfree_checkout(
    request: Request,
    order_id: int = Form(...),
    return_url: str = Form(default=""),
    payment_method: str = Form(default="upi"),
):
    user_id = require_api_user_id(request)
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
        if not order:
            return {"error": "Order not found"}

        normalized_method = normalize_payment_method(payment_method)
        if normalized_method == "cash":
            return {"error": "Cash orders do not require online checkout"}

        charge_amount = round(float(order.total_amount or 0.0), 2)
        minimum_floor = gateway_checkout_minimum_inr(normalized_method)
        if charge_amount < minimum_floor:
            charge_amount = round(minimum_floor, 2)

        if not return_url:
            base_url = str(request.base_url).rstrip("/")
            return_url = f"{base_url}/payment-success?order_id={order_id}&cf_order_id={{order_id}}"

        cashfree_order = create_cashfree_order(
            amount=charge_amount,
            order_id=order_id,
            return_url=return_url,
            payment_method=normalized_method,
        )
        if not cashfree_order:
            return {"error": "Failed to create Cashfree order"}

        return {
            "provider": "cashfree",
            "cashfree": {
                "order_id": cashfree_order.get("cashfree_order_id"),
                "cf_order_id": cashfree_order.get("cf_order_id"),
                "payment_session_id": cashfree_order.get("payment_session_id"),
                "payment_link": cashfree_order.get("payment_link"),
            },
        }
    finally:
        db.close()


@router.get("/order/{cashfree_order_id}")
def get_order(cashfree_order_id: str):
    """Retrieve Cashfree order details."""
    order = get_cashfree_order(cashfree_order_id)
    if not order:
        return {"error": "Cashfree order not found"}

    return {
        "cashfree_order_id": order.get("order_id"),
        "cf_order_id": order.get("cf_order_id"),
        "order_status": order.get("order_status"),
        "order_amount": order.get("order_amount"),
    }


@router.post("/process")
def process_payment(
    request: Request,
    order_id: int = Form(...),
    amount: float = Form(...),
    method: str = Form(default="upi"),
):
    user_id = require_api_user_id(request)
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
        if not order:
            return {"error": "Order not found"}

        normalized_method = normalize_payment_method(method)
        expected_amount = round(float(order.total_amount or 0.0), 2)
        received_amount = round(float(amount or 0.0), 2)
        if expected_amount <= 0:
            return {"error": "Invalid order amount"}

        if abs(received_amount - expected_amount) > 0.01:
            return {
                "error": "Amount mismatch",
                "expected_amount": expected_amount,
                "received_amount": received_amount,
            }

        existing_completed = (
            db.query(Payment)
            .filter(Payment.order_id == order_id, Payment.status == "completed")
            .first()
        )
        if existing_completed:
            return {
                "success": True,
                "payment_id": existing_completed.id,
                "order_id": order_id,
                "already_processed": True,
            }

        payment = Payment(
            order_id=order_id,
            amount=expected_amount,
            method=normalized_method,
            status="completed",
        )
        db.add(payment)

        order.status = "paid"
        order.payment_method = normalized_method
        record_audit_event(
            db,
            event_type="payment.manual.completed",
            message=f"Manual payment completed for order #{order.id}",
            user_id=user_id,
            order_id=order.id,
            metadata={
                "payment_method": normalized_method,
                "amount": expected_amount,
            },
        )
        db.commit()
        clear_cart(user_id=user_id)

        return {
            "success": True,
            "payment_id": payment.id,
            "order_id": order_id,
        }
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()


@router.post("/cashfree-verify")
def cashfree_verify(
    request: Request,
    order_id: int = Form(...),
    cashfree_order_id: str = Form(...),
):
    """Verify Cashfree payment completion."""
    user_id = require_api_user_id(request)
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
        if not order:
            return {"error": "Order not found"}

        paid, payment_info = has_successful_cashfree_payment(cashfree_order_id)
        if not paid:
            return {"error": "Payment not completed", "status": "pending"}

        payment = (
            db.query(Payment)
            .filter(Payment.order_id == order_id)
            .order_by(Payment.id.desc())
            .first()
        )
        if not payment:
            return {"error": "Payment record not found"}

        payment.status = "completed"
        payment.transaction_id = str(payment_info.get("cf_payment_id") or cashfree_order_id)
        payment.payment_data = json.dumps({
            "provider": "cashfree",
            "cashfree_order_id": cashfree_order_id,
            "payment_status": payment_info.get("payment_status"),
            "payment_group": payment_info.get("payment_group"),
            "payment_method": payment_info.get("payment_method"),
            "verified": True,
        })
        order.status = "paid"
        record_audit_event(
            db,
            event_type="payment.cashfree.verified",
            message=f"Cashfree payment verified for order #{order.id}",
            user_id=user_id,
            order_id=order.id,
            metadata={
                "cashfree_order_id": cashfree_order_id,
                "cashfree_payment_id": payment_info.get("cf_payment_id"),
            },
        )
        db.commit()
        clear_cart(user_id=user_id)

        base_url = str(request.base_url).rstrip("/")
        return {
            "success": True,
            "checkout_url": f"{base_url}/payment-success?order_id={order_id}",
        }
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()
