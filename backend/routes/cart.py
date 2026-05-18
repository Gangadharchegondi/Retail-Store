"""Cart routes - Manage shopping cart operations."""
from fastapi import APIRouter, Form, Request
from backend.services.cart import (
    get_cart_data,
    add_to_cart,
    clear_cart,
    update_quantity,
    get_cart_count,
)
from backend.database import SessionLocal
from backend.models import Product
from backend.session_auth import require_api_user_id

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("")
@router.get("/")
def get_cart(request: Request):
    """Get current cart contents and totals."""
    user_id = require_api_user_id(request)
    return get_cart_data(user_id=user_id)


@router.get("/count")
def cart_count(request: Request):
    """Get total number of items in cart."""
    user_id = require_api_user_id(request)
    return {"count": get_cart_count(user_id=user_id)}


@router.post("/add")
def add_item(request: Request, product_id: int = Form(...)):
    """Add product to cart by ID."""
    user_id = require_api_user_id(request)
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}
        
        add_to_cart(product, user_id=user_id)
        return {"success": True, "product": product.name}
    finally:
        db.close()


@router.post("/update")
def update_item(request: Request, item_name: str = Form(...), quantity: int = Form(...)):
    """Update quantity of cart item."""
    user_id = require_api_user_id(request)
    if quantity < 0:
        return {"error": "Quantity cannot be negative"}
    
    update_quantity(item_name, quantity, user_id=user_id)
    return {"success": True, "quantity": quantity}


@router.post("/clear")
def clear(request: Request):
    """Clear all items from cart."""
    user_id = require_api_user_id(request)
    clear_cart(user_id=user_id)
    return {"success": True, "message": "Cart cleared"}
