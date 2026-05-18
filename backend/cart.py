import threading

# In-memory session state
cart_items = []
_cart_lock = threading.RLock()


def get_cart_data():
    from backend.weight_sensor import check_theft_status

    with _cart_lock:
        items_snapshot = [item.copy() for item in cart_items]

    total = sum(item["price"] * item["qty"] for item in items_snapshot)
    expected_weight = sum(item["weight"] * item["qty"] for item in items_snapshot)

    return {
        "items": items_snapshot,
        "total": total,
        "expected_weight": expected_weight,
        "security": check_theft_status(expected_weight)
    }


def add_to_cart_logic(product_obj):
    """Updates the internal list of items in the current session."""
    with _cart_lock:
        for item in cart_items:
            if item["name"] == product_obj.name:
                item["qty"] += 1
                return

        cart_items.append({
            "name": product_obj.name,
            "price": product_obj.price,
            "category": product_obj.category,
            "weight": product_obj.weight,
            "qty": 1
        })


def clear_cart():
    global cart_items
    with _cart_lock:
        cart_items = []


def update_quantity(item_name, new_qty):
    global cart_items
    with _cart_lock:
        if new_qty <= 0:
            cart_items = [item for item in cart_items if item["name"] != item_name]
        else:
            for item in cart_items:
                if item["name"] == item_name:
                    item["qty"]= new_qty
                    break
