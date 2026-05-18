"""
Database seeding script - Initialize database with sample products
Run with: python -m backend.scripts.seed_database
"""
from backend.database import engine, SessionLocal
from backend.models import Product, Base


def seed_database():
    """Seed database with sample products."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    products_data = [
        {
            "barcode": "8901491101844",
            "name": "Lays Magic Masala",
            "category": "Snacks",
            "price": 20.0,
            "weight": 50.0,
            "stock": 100
        },
        {
            "barcode": "8901234567001",
            "name": "Kurkure Masala Munch",
            "category": "Snacks",
            "price": 25.0,
            "weight": 60.0,
            "stock": 80
        },
        {
            "barcode": "8901234567002",
            "name": "Britannia Good Day",
            "category": "Snacks",
            "price": 30.0,
            "weight": 120.0,
            "stock": 65
        },
        {
            "barcode": "8906007281580",
            "name": "Coca Cola 500ml",
            "category": "Drinks",
            "price": 40.0,
            "weight": 500.0,
            "stock": 50
        },
        {
            "barcode": "8901234567003",
            "name": "Pepsi 500ml",
            "category": "Drinks",
            "price": 40.0,
            "weight": 500.0,
            "stock": 55
        },
        {
            "barcode": "0041331021529",
            "name": "Classic Coca Cola",
            "category": "Drinks",
            "price": 35.0,
            "weight": 355.0,
            "stock": 40
        },
        {
            "barcode": "9780545010221",
            "name": "Harry Potter Book",
            "category": "Books",
            "price": 499.0,
            "weight": 400.0,
            "stock": 25
        },
        {
            "barcode": "9780141439518",
            "name": "Pride and Prejudice",
            "category": "Books",
            "price": 299.0,
            "weight": 350.0,
            "stock": 20
        },
        {
            "barcode": "8901234567004",
            "name": "Wireless Earbuds",
            "category": "Electronics",
            "price": 1299.0,
            "weight": 150.0,
            "stock": 15
        },
        {
            "barcode": "8901234567005",
            "name": "USB-C Fast Charger",
            "category": "Electronics",
            "price": 899.0,
            "weight": 90.0,
            "stock": 30
        },
        {
            "barcode": "8901234567006",
            "name": "Dishwash Liquid",
            "category": "Household",
            "price": 110.0,
            "weight": 500.0,
            "stock": 45
        },
        {
            "barcode": "8901234567007",
            "name": "Notebook Pack",
            "category": "Stationery",
            "price": 75.0,
            "weight": 300.0,
            "stock": 70
        },
        {
            "barcode": "8901234567008",
            "name": "Detergent Powder",
            "category": "Household",
            "price": 150.0,
            "weight": 1000.0,
            "stock": 35
        },
        {
            "barcode": "8901234567009",
            "name": "Ball Pen Pack",
            "category": "Stationery",
            "price": 50.0,
            "weight": 80.0,
            "stock": 90
        },
        {
            "barcode": "8901234567010",
            "name": "Fresh Apples 1kg",
            "category": "Fresh",
            "price": 180.0,
            "weight": 1000.0,
            "stock": 25
        },
        {
            "barcode": "8901234567011",
            "name": "Green Tea Pack",
            "category": "Drinks",
            "price": 220.0,
            "weight": 100.0,
            "stock": 30
        },
        {
            "barcode": "8901234567012",
            "name": "Chocolate Wafer",
            "category": "Snacks",
            "price": 45.0,
            "weight": 110.0,
            "stock": 75
        },
        {
            "barcode": "8901030862101",
            "name": "Hide and Seek Biscuit",
            "category": "Snacks",
            "price": 35.0,
            "weight": 120.0,
            "stock": 72
        },
        {
            "barcode": "8901063161458",
            "name": "Uncle Chipps Spicy Treat",
            "category": "Snacks",
            "price": 20.0,
            "weight": 55.0,
            "stock": 68
        },
        {
            "barcode": "8901725131029",
            "name": "Bingo Mad Angles",
            "category": "Snacks",
            "price": 25.0,
            "weight": 72.0,
            "stock": 64
        },
        {
            "barcode": "8901491304009",
            "name": "Doritos Nacho Chips",
            "category": "Snacks",
            "price": 50.0,
            "weight": 82.0,
            "stock": 58
        },
        {
            "barcode": "8906017293010",
            "name": "Haldiram Bhujia",
            "category": "Snacks",
            "price": 65.0,
            "weight": 150.0,
            "stock": 54
        },
        {
            "barcode": "8901725956011",
            "name": "Too Yumm Multigrain Chips",
            "category": "Snacks",
            "price": 30.0,
            "weight": 70.0,
            "stock": 60
        },
        {
            "barcode": "8901491501023",
            "name": "Peri Peri Peanuts",
            "category": "Snacks",
            "price": 40.0,
            "weight": 95.0,
            "stock": 63
        },
        {
            "barcode": "8901234705512",
            "name": "Cheese Crackers",
            "category": "Snacks",
            "price": 55.0,
            "weight": 110.0,
            "stock": 48
        },
        {
            "barcode": "8901764030287",
            "name": "Red Bull Energy Drink",
            "category": "Drinks",
            "price": 125.0,
            "weight": 250.0,
            "stock": 34
        },
        {
            "barcode": "8908019331475",
            "name": "Paper Boat Aamras",
            "category": "Drinks",
            "price": 40.0,
            "weight": 250.0,
            "stock": 49
        },
        {
            "barcode": "8902080039050",
            "name": "Tropicana Orange Juice",
            "category": "Drinks",
            "price": 99.0,
            "weight": 1000.0,
            "stock": 28
        },
        {
            "barcode": "9780061120084",
            "name": "To Kill a Mockingbird",
            "category": "Books",
            "price": 349.0,
            "weight": 300.0,
            "stock": 24
        },
        {
            "barcode": "9788172234980",
            "name": "Wings of Fire",
            "category": "Books",
            "price": 225.0,
            "weight": 280.0,
            "stock": 31
        },
        {
            "barcode": "9789356291078",
            "name": "Atomic Habits",
            "category": "Books",
            "price": 499.0,
            "weight": 320.0,
            "stock": 22
        },
        {
            "barcode": "9789387779361",
            "name": "Ikigai",
            "category": "Books",
            "price": 399.0,
            "weight": 250.0,
            "stock": 27
        },
        {
            "barcode": "8907605107014",
            "name": "Bluetooth Speaker",
            "category": "Electronics",
            "price": 1499.0,
            "weight": 480.0,
            "stock": 18
        },
        {
            "barcode": "8904333112142",
            "name": "Power Bank 10000mAh",
            "category": "Electronics",
            "price": 999.0,
            "weight": 220.0,
            "stock": 26
        },
        {
            "barcode": "8906093560022",
            "name": "LED Desk Lamp",
            "category": "Electronics",
            "price": 699.0,
            "weight": 520.0,
            "stock": 19
        },
        {
            "barcode": "8908018011293",
            "name": "Type-C Data Cable",
            "category": "Electronics",
            "price": 249.0,
            "weight": 60.0,
            "stock": 52
        },
        {
            "barcode": "8901030655116",
            "name": "Floor Cleaner",
            "category": "Household",
            "price": 189.0,
            "weight": 1000.0,
            "stock": 29
        },
        {
            "barcode": "8901725135454",
            "name": "Toilet Cleaner",
            "category": "Household",
            "price": 98.0,
            "weight": 500.0,
            "stock": 44
        },
        {
            "barcode": "8908001158066",
            "name": "Garbage Bags Pack",
            "category": "Household",
            "price": 120.0,
            "weight": 300.0,
            "stock": 37
        },
        {
            "barcode": "8901363010090",
            "name": "Glass Cleaner Spray",
            "category": "Household",
            "price": 145.0,
            "weight": 500.0,
            "stock": 33
        }
    ]

    for product_data in products_data:
        existing_product = db.query(Product).filter(Product.barcode == product_data["barcode"]).first()
        if existing_product:
            existing_product.name = product_data["name"]
            existing_product.category = product_data["category"]
            existing_product.price = product_data["price"]
            existing_product.weight = product_data["weight"]
            existing_product.stock = product_data["stock"]
        else:
            product = Product(**product_data)
            db.add(product)
    
    db.commit()
    db.close()
    print(f"✅ Database seeded with {len(products_data)} sample products.")


if __name__ == "__main__":
    seed_database()
