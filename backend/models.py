from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime, timezone


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String, unique=True, index=True)
    name = Column(String)
    category = Column(String)
    price = Column(Float)
    weight = Column(Float)
    stock = Column(Integer)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    password = Column(String)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(Float)
    status = Column(String, default="pending")  # pending, paid, cancelled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    payment_method = Column(String)  # cash, card, digital_wallet

    user = relationship("User")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_name = Column(String)
    product_category = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    weight = Column(Float)

    order = relationship("Order", back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    amount = Column(Float)
    method = Column(String)  # cash, card, digital_wallet
    status = Column(String, default="pending")  # pending, completed, failed
    transaction_id = Column(String, nullable=True)
    payment_data = Column(Text, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    product_name = Column(String)
    product_category = Column(String)
    price = Column(Float)
    weight = Column(Float)
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    product = relationship("Product")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=True)
    event_type = Column(String, index=True)
    message = Column(String)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User")
    order = relationship("Order")