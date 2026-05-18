from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import app
from backend.database import SessionLocal
from backend.models import AuditEvent, CartItem, Order, OrderItem, Payment, User


client = TestClient(app)


def _register_and_login_unique_user() -> User:
    unique = f"test-{uuid4().hex[:8]}"
    email = f"{unique}@example.com"

    response = client.post(
        "/auth/register",
        data={
            "username": unique,
            "email": email,
            "password": "strong-pass-123",
        },
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        return user
    finally:
        db.close()


def _create_order_for_user(user_id: int, status: str = "pending", payment_status: str = "pending") -> int:
    db = SessionLocal()
    try:
        order = Order(user_id=user_id, total_amount=210.0, status=status, payment_method="upi")
        db.add(order)
        db.flush()

        db.add(OrderItem(order_id=order.id, product_name="Rice", product_category="Grocery", price=100.0, quantity=2, weight=2.0))
        db.add(Payment(order_id=order.id, amount=210.0, method="upi", status=payment_status, transaction_id=f"tx-{order.id}"))
        db.commit()
        return order.id
    finally:
        db.close()


def test_payment_success_callback_marks_order_paid(monkeypatch):
    user = _register_and_login_unique_user()
    order_id = _create_order_for_user(user.id, status="pending", payment_status="pending")

    db = SessionLocal()
    try:
        db.add(
            CartItem(
                user_id=user.id,
                product_id=9999,
                product_name="Pending Cart Item",
                product_category="General",
                price=10.0,
                weight=0.2,
                quantity=2,
            )
        )
        db.commit()
    finally:
        db.close()

    def fake_successful_payment(_: str):
        return True, {"cf_payment_id": f"cf-pay-{int(time.time())}"}

    monkeypatch.setattr("backend.routes.pages.has_successful_cashfree_payment", fake_successful_payment)

    response = client.get(f"/payment-success?order_id={order_id}&cf_order_id=cf-order-test")
    assert response.status_code == 200
    assert "Download Bill" in response.text

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        payment = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.id.desc()).first()
        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.order_id == order_id, AuditEvent.event_type == "payment.cashfree.callback_verified")
            .order_by(AuditEvent.id.desc())
            .first()
        )

        assert order is not None and order.status == "paid"
        assert payment is not None and payment.status == "completed"
        assert audit is not None
        assert db.query(CartItem).filter(CartItem.user_id == user.id).count() == 0
    finally:
        db.close()


def test_bill_pdf_download_returns_pdf_and_audit_event():
    user = _register_and_login_unique_user()
    order_id = _create_order_for_user(user.id, status="paid", payment_status="completed")

    response = client.get(f"/payment-success/bill.pdf?order_id={order_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")

    db = SessionLocal()
    try:
        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.order_id == order_id, AuditEvent.event_type == "invoice.pdf.generated")
            .order_by(AuditEvent.id.desc())
            .first()
        )
        assert audit is not None
    finally:
        db.close()


def test_orders_page_supports_filter_and_pagination():
    user = _register_and_login_unique_user()

    db = SessionLocal()
    try:
        for index in range(15):
            order = Order(
                user_id=user.id,
                total_amount=50 + index,
                status="paid" if index % 2 == 0 else "pending",
                payment_method="upi",
            )
            db.add(order)
            db.flush()
            db.add(OrderItem(order_id=order.id, product_name=f"Item {index}", product_category="General", price=10.0, quantity=1, weight=0.2))
            db.add(Payment(order_id=order.id, amount=50 + index, method="upi", status="completed" if index % 2 == 0 else "pending", transaction_id=f"bulk-{order.id}"))
        db.commit()
    finally:
        db.close()

    response = client.get("/orders?page=1&page_size=5&status=pending")
    assert response.status_code == 200
    assert "orders-table-body" in response.text
    assert "skeleton" in response.text

    api_response = client.get("/api/orders/history?page=1&page_size=5&status=pending")
    assert api_response.status_code == 200
    payload = api_response.json()
    assert payload["pagination"]["total_pages"] >= 2
    assert len(payload["orders"]) <= 5


def test_payment_success_callback_failed_marks_order_failed(monkeypatch):
    user = _register_and_login_unique_user()
    order_id = _create_order_for_user(user.id, status="pending", payment_status="pending")

    def fake_failed_payment(_: str):
        return False, {"payment_status": "FAILED", "cf_payment_id": f"cf-fail-{int(time.time())}"}

    monkeypatch.setattr("backend.routes.pages.has_successful_cashfree_payment", fake_failed_payment)

    response = client.get(f"/payment-success?order_id={order_id}&cf_order_id=cf-order-failed")
    assert response.status_code == 200

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        payment = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.id.desc()).first()
        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.order_id == order_id, AuditEvent.event_type == "payment.cashfree.callback_failed")
            .order_by(AuditEvent.id.desc())
            .first()
        )
        assert order is not None and order.status == "failed"
        assert payment is not None and payment.status == "failed"
        assert audit is not None
    finally:
        db.close()


def test_payment_success_callback_expired_marks_order_failed(monkeypatch):
    user = _register_and_login_unique_user()
    order_id = _create_order_for_user(user.id, status="pending", payment_status="pending")

    def fake_expired_payment(_: str):
        return False, {"payment_status": "EXPIRED", "cf_payment_id": f"cf-exp-{int(time.time())}"}

    monkeypatch.setattr("backend.routes.pages.has_successful_cashfree_payment", fake_expired_payment)

    response = client.get(f"/payment-success?order_id={order_id}&cf_order_id=cf-order-expired")
    assert response.status_code == 200

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        payment = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.id.desc()).first()
        assert order is not None and order.status == "failed"
        assert payment is not None and payment.status == "failed"
    finally:
        db.close()


def test_payment_success_callback_duplicate_is_idempotent(monkeypatch):
    user = _register_and_login_unique_user()
    order_id = _create_order_for_user(user.id, status="pending", payment_status="pending")

    db = SessionLocal()
    try:
        db.add(
            CartItem(
                user_id=user.id,
                product_id=9998,
                product_name="Replay Test Item",
                product_category="General",
                price=20.0,
                weight=0.3,
                quantity=1,
            )
        )
        db.commit()
    finally:
        db.close()

    callback_payment_id = f"cf-replay-{int(time.time())}"

    def fake_successful_payment(_: str):
        return True, {"cf_payment_id": callback_payment_id}

    monkeypatch.setattr("backend.routes.pages.has_successful_cashfree_payment", fake_successful_payment)

    first = client.get(f"/payment-success?order_id={order_id}&cf_order_id=cf-order-dup")
    second = client.get(f"/payment-success?order_id={order_id}&cf_order_id=cf-order-dup")
    assert first.status_code == 200
    assert second.status_code == 200

    db = SessionLocal()
    try:
        callback_audits = (
            db.query(AuditEvent)
            .filter(AuditEvent.order_id == order_id, AuditEvent.event_type == "payment.cashfree.callback_verified")
            .all()
        )
        payment = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.id.desc()).first()
        order = db.query(Order).filter(Order.id == order_id).first()

        assert len(callback_audits) == 1
        assert order is not None and order.status == "paid"
        assert payment is not None and payment.status == "completed"
        assert str(payment.transaction_id) == callback_payment_id
        assert db.query(CartItem).filter(CartItem.user_id == user.id).count() == 0
    finally:
        db.close()
