"""
Product routes - Product listing and management
"""
from fastapi import APIRouter, Query, Form
from backend.database import SessionLocal
from backend.models import Product

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/")
def list_products(skip: int = Query(0), limit: int = Query(100)):
    """Get list of all products with optional pagination."""
    db = SessionLocal()
    try:
        products = db.query(Product).offset(skip).limit(limit).all()
        return {
            "products": [
                {
                    "id": p.id,
                    "barcode": p.barcode,
                    "name": p.name,
                    "category": p.category,
                    "price": p.price,
                    "weight": p.weight,
                    "stock": p.stock,
                }
                for p in products
            ]
        }
    finally:
        db.close()


@router.get("/stats")
def product_stats():
    """Get inventory summary for the catalog."""
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        total_products = len(products)
        in_stock = sum(1 for product in products if (product.stock or 0) > 0)
        out_of_stock = total_products - in_stock
        low_stock = sum(1 for product in products if 0 < (product.stock or 0) <= 5)

        return {
            "totalProducts": total_products,
            "inStock": in_stock,
            "outOfStock": out_of_stock,
            "lowStock": low_stock,
        }
    finally:
        db.close()


@router.get("/search")
def search_products(q: str = Query(...)):
    """Search products by name or category."""
    db = SessionLocal()
    try:
        products = db.query(Product).filter(
            (Product.name.ilike(f"%{q}%")) | (Product.category.ilike(f"%{q}%"))
        ).all()
        return {
            "products": [
                {
                    "id": p.id,
                    "barcode": p.barcode,
                    "name": p.name,
                    "category": p.category,
                    "price": p.price,
                    "weight": p.weight,
                    "stock": p.stock,
                }
                for p in products
            ]
        }
    finally:
        db.close()


@router.get("/{product_id}")
def get_product(product_id: int):
    """Get detailed information about a specific product."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}
        
        return {
            "id": product.id,
            "barcode": product.barcode,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "weight": product.weight,
            "stock": product.stock,
        }
    finally:
        db.close()


@router.post("/adjust-stock")
def adjust_stock(product_id: int = Form(...), delta: int = Form(...)):
    """Adjust product stock up or down and return the updated stock."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}

        current_stock = int(product.stock or 0)
        new_stock = current_stock + int(delta)

        if new_stock < 0:
            return {"error": "Insufficient stock", "stock": current_stock}

        product.stock = new_stock
        db.commit()

        return {
            "success": True,
            "product_id": product.id,
            "stock": product.stock,
        }
    finally:
        db.close()
