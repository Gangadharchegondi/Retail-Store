"""
SmartRetail - FastAPI Application
Main application entry point with middleware, routes, and static file setup
"""
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import traceback

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

# Import configuration
from backend.config import (
    ALLOWED_ORIGINS,
    STATIC_DIR,
    TEMPLATES_DIR,
    SESSION_SECRET_KEY,
    SESSION_MAX_AGE_SECONDS,
)

# Import route modules
from backend.routes import auth, pages, products, cart, payment
from backend.services.camera import generate_frames, pop_last_product
from backend.services.cart import get_cart_data, clear_cart, update_quantity
from backend.database import SessionLocal
from backend.models import Order, OrderItem, Payment, Product
from backend.session_auth import require_api_user_id

# ========================
# APPLICATION SETUP
# ========================
app = FastAPI(
    title="SmartRetail API",
    description="AI-powered smart retail store management system",
    version="1.0.0"
)

# ========================
# MIDDLEWARE SETUP
# ========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=False,
)

# ========================
# STATIC FILES & TEMPLATES
# ========================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
pages.set_templates(templates)

# ========================
# ROUTE REGISTRATION
# ========================
app.include_router(pages.router)          # Page templates
app.include_router(auth.router)           # Authentication
app.include_router(products.router)       # Products API
app.include_router(cart.router)           # Cart API
app.include_router(payment.router)        # Payment API


@app.post("/login")
def login_compat(request: Request, email: str = Form(...), password: str = Form(...)):
    """Compatibility login endpoint for the existing form action."""
    return auth.login(request=request, email=email, password=password)


@app.post("/register")
def register_compat(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    """Compatibility register endpoint for the existing form action."""
    return auth.register(request=request, username=username, email=email, password=password)


@app.post("/api/pay")
def pay_compat(
    request: Request,
    payment_method: str = Form(default="upi"),
    upi_id: str = Form(default=""),
):
    """Compatibility endpoint used by payment page JS."""
    return payment.checkout_from_cart(request=request, payment_method=payment_method, upi_id=upi_id)


@app.get("/api/scan_alert")
def scan_alert_compat(request: Request):
    """Compatibility endpoint consumed by the scanner UI."""
    user_id = require_api_user_id(request)
    product = pop_last_product()
    if not product:
        return {"status": "idle", "cart": get_cart_data(user_id=user_id)}

    if isinstance(product, dict):
        product_payload = {
            "id": product.get("id"),
            "name": product.get("name"),
            "price": product.get("price"),
            "category": product.get("category"),
            "weight": product.get("weight"),
        }
    else:
        product_payload = {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "category": product.category,
            "weight": product.weight,
        }

    return {
        "status": "scanned",
        "product": product_payload,
        "cart": get_cart_data(user_id=user_id),
    }


@app.post("/api/clear_cart")
def clear_cart_compat(request: Request):
    """Compatibility endpoint for scanner clear-cart action."""
    user_id = require_api_user_id(request)
    clear_cart(user_id=user_id)
    return {"status": "cleared", "cart": get_cart_data(user_id=user_id)}


@app.post("/api/update_quantity")
def update_quantity_compat(request: Request, item_name: str = Form(...), quantity: int = Form(...)):
    """Compatibility endpoint for scanner quantity updates."""
    user_id = require_api_user_id(request)
    update_quantity(item_name, quantity, user_id=user_id)
    return {"status": "updated", "cart": get_cart_data(user_id=user_id)}


@app.get("/api/dashboard-stats")
def dashboard_stats(request: Request):
    """Return live dashboard metrics including inventory counts."""
    user_id = require_api_user_id(request)
    db = SessionLocal()
    try:
        total_products = db.query(Product).count()
        in_stock = db.query(Product).filter(Product.stock > 0).count()

        recent_orders = (
            db.query(Order)
            .filter(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(5)
            .all()
        )

        order_ids = [order.id for order in recent_orders]
        item_counts = {}
        if order_ids:
            rows = (
                db.query(OrderItem.order_id, OrderItem.quantity)
                .filter(OrderItem.order_id.in_(order_ids))
                .all()
            )
            for order_id, quantity in rows:
                item_counts[order_id] = item_counts.get(order_id, 0) + int(quantity or 0)

        # Fetch latest payment row per recent order to render current status/method/amount.
        latest_recent_payments = {}
        if order_ids:
            payment_rows = (
                db.query(Payment)
                .filter(Payment.order_id.in_(order_ids))
                .order_by(Payment.order_id.asc(), Payment.id.desc())
                .all()
            )
            for payment in payment_rows:
                if payment.order_id not in latest_recent_payments:
                    latest_recent_payments[payment.order_id] = payment

        total_orders = db.query(Order).filter(Order.user_id == user_id).count()

        # Treat multiple success labels as paid to support mixed historical records.
        paid_payment_statuses = {"completed", "paid", "success"}
        total_spent = 0.0

        all_orders = db.query(Order).filter(Order.user_id == user_id).all()
        for order in all_orders:
            latest_payment = (
                db.query(Payment)
                .filter(Payment.order_id == order.id)
                .order_by(Payment.id.desc())
                .first()
            )

            if latest_payment and str(latest_payment.status or "").strip().lower() in paid_payment_statuses:
                total_spent += float(latest_payment.amount or order.total_amount or 0.0)
                continue

            if str(order.status or "").strip().lower() == "paid":
                total_spent += float(order.total_amount or 0.0)

        return {
            "totalOrders": total_orders,
            "totalSpent": round(total_spent, 2),
            "totalProducts": total_products,
            "inStock": in_stock,
            "recentOrders": [
                {
                    "id": order.id,
                    "itemCount": item_counts.get(order.id, 0),
                    "total": float((latest_recent_payments.get(order.id).amount if latest_recent_payments.get(order.id) else None) or order.total_amount or 0.0),
                    "status": (
                        latest_recent_payments.get(order.id).status
                        if latest_recent_payments.get(order.id) and latest_recent_payments.get(order.id).status
                        else order.status
                    ) or "pending",
                    "date": order.created_at.isoformat() if order.created_at else None,
                }
                for order in recent_orders
            ],
        }
    finally:
        db.close()

# ========================
# CAMERA & STREAMING
# ========================
@app.get("/video_feed")
async def video_feed(request: Request):
    """Stream video from camera with barcode detection."""
    try:
        return StreamingResponse(
            generate_frames(request),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# ========================
# HEALTH CHECKS
# ========================
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/health")
async def api_health():
    """API health check endpoint."""
    return {"status": "ok", "service": "smartretail"}