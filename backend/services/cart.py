"""Persistent cart service module backed by the database."""

from backend.database import SessionLocal
from backend.models import CartItem
from backend.services.weight_sensor import check_theft_status


def _normalized_user_id(user_id) -> int:
    try:
        return int(user_id)
    except (TypeError, ValueError):
        raise ValueError("user_id is required for cart operations")


def _cart_item_to_payload(item: CartItem) -> dict:
    return {
        "name": item.product_name,
        "price": float(item.price or 0.0),
        "category": item.product_category,
        "weight": float(item.weight or 0.0),
        "qty": int(item.quantity or 0),
        "product_id": item.product_id,
    }


def _load_user_cart(db, user_id: int):
    return (
        db.query(CartItem)
        .filter(CartItem.user_id == user_id)
        .order_by(CartItem.id.asc())
        .all()
    )


def get_cart_data(user_id=None):
    """Get current cart data including items, totals, and security status."""
    scoped_user_id = _normalized_user_id(user_id)
    db = SessionLocal()
    try:
        items = _load_user_cart(db, scoped_user_id)
        payload_items = [_cart_item_to_payload(item) for item in items]
        total = sum(item["price"] * item["qty"] for item in payload_items)
        expected_weight = sum(item["weight"] * item["qty"] for item in payload_items)

        return {
            "items": payload_items,
            "total": total,
            "expected_weight": expected_weight,
            "security": check_theft_status(expected_weight),
        }
    finally:
        db.close()


def add_to_cart(product_obj, user_id=None):
    """Add product to cart or increment quantity if already present."""
    scoped_user_id = _normalized_user_id(user_id)
    db = SessionLocal()
    try:
        cart_item = (
            db.query(CartItem)
            .filter(
                CartItem.user_id == scoped_user_id,
                CartItem.product_id == product_obj.id,
            )
            .first()
        )

        if cart_item:
            cart_item.quantity = int(cart_item.quantity or 0) + 1
        else:
            cart_item = CartItem(
                user_id=scoped_user_id,
                product_id=product_obj.id,
                product_name=product_obj.name,
                product_category=product_obj.category,
                price=product_obj.price,
                weight=product_obj.weight,
                quantity=1,
            )
            db.add(cart_item)

        db.commit()
    finally:
        db.close()


def clear_cart(user_id=None):
    """Clear all items from cart."""
    scoped_user_id = _normalized_user_id(user_id)
    db = SessionLocal()
    try:
        db.query(CartItem).filter(CartItem.user_id == scoped_user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def update_quantity(item_name, new_qty, user_id=None):
    """Update quantity of an item or remove if quantity <= 0."""
    scoped_user_id = _normalized_user_id(user_id)
    db = SessionLocal()
    try:
        item = (
            db.query(CartItem)
            .filter(CartItem.user_id == scoped_user_id, CartItem.product_name == item_name)
            .first()
        )
        if not item:
            return

        if new_qty <= 0:
            db.delete(item)
        else:
            item.quantity = int(new_qty)
        db.commit()
    finally:
        db.close()


def get_cart_count(user_id=None):
    """Get total number of items in cart."""
    scoped_user_id = _normalized_user_id(user_id)
    db = SessionLocal()
    try:
        items = _load_user_cart(db, scoped_user_id)
        return sum(int(item.quantity or 0) for item in items)
    finally:
        db.close()


def get_cart_items(user_id=None):
    """Get copy of all cart items."""
    scoped_user_id = _normalized_user_id(user_id)
    db = SessionLocal()
    try:
        return [_cart_item_to_payload(item) for item in _load_user_cart(db, scoped_user_id)]
    finally:
        db.close()


def reset_cart_store():
    """Remove all persisted cart items (used by tests)."""
    db = SessionLocal()
    try:
        db.query(CartItem).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
