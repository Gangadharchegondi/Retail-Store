"""Cashfree payment helpers for SmartRetail."""

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "").strip()
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "").strip()
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "sandbox").strip().lower()
CASHFREE_API_VERSION = os.getenv("CASHFREE_API_VERSION", "2023-08-01").strip()

CASHFREE_ENABLED = bool(CASHFREE_APP_ID and CASHFREE_SECRET_KEY)

if CASHFREE_ENV == "production":
    CASHFREE_BASE_URL = "https://api.cashfree.com"
    CASHFREE_MODE = "production"
else:
    CASHFREE_BASE_URL = "https://sandbox.cashfree.com"
    CASHFREE_MODE = "sandbox"


def _cashfree_headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "x-api-version": CASHFREE_API_VERSION,
    }


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def create_cashfree_order(
    amount: float,
    order_id: int,
    return_url: str,
    customer_name: str = "SmartRetail Customer",
    customer_email: str = "customer@smartretail.local",
    customer_phone: str = "9999999999",
    payment_method: str = "upi",
):
    if not CASHFREE_ENABLED:
        print("Cashfree checkout requested but API keys are not configured")
        return None

    amount_inr = round(float(amount or 0.0), 2)
    if amount_inr <= 0:
        raise ValueError("Amount must be greater than zero")

    cashfree_order_id = f"sr-{order_id}-{int(time.time())}"

    payload = {
        "order_id": cashfree_order_id,
        "order_amount": amount_inr,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": f"user-{order_id}",
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
        },
        "order_meta": {
            "return_url": return_url,
            "payment_methods": payment_method,
        },
        "order_note": f"SmartRetail Order #{order_id}",
    }

    try:
        response = requests.post(
            f"{CASHFREE_BASE_URL}/pg/orders",
            headers=_cashfree_headers(),
            json=payload,
            timeout=20,
        )
        response_payload = _safe_json(response)

        if response.status_code >= 400:
            print("CASHFREE CREATE ORDER ERROR:", response_payload or response.text)
            return None

        return {
            "cashfree_order_id": response_payload.get("order_id") or cashfree_order_id,
            "cf_order_id": response_payload.get("cf_order_id"),
            "order_status": response_payload.get("order_status"),
            "payment_session_id": response_payload.get("payment_session_id"),
            "payment_link": response_payload.get("payment_link"),
            "raw": response_payload,
        }
    except Exception as exc:
        print("CASHFREE CREATE ORDER EXCEPTION:", str(exc))
        return None


def get_cashfree_order(cashfree_order_id: str):
    if not CASHFREE_ENABLED:
        return None

    try:
        response = requests.get(
            f"{CASHFREE_BASE_URL}/pg/orders/{cashfree_order_id}",
            headers=_cashfree_headers(),
            timeout=20,
        )
        payload = _safe_json(response)

        if response.status_code >= 400:
            return None

        return payload
    except Exception:
        return None


def get_cashfree_order_payments(cashfree_order_id: str):
    if not CASHFREE_ENABLED:
        return []

    try:
        response = requests.get(
            f"{CASHFREE_BASE_URL}/pg/orders/{cashfree_order_id}/payments",
            headers=_cashfree_headers(),
            timeout=20,
        )
        payload = response.json()
        if response.status_code >= 400:
            return []
        if isinstance(payload, list):
            return payload
        return []
    except Exception:
        return []


def has_successful_cashfree_payment(cashfree_order_id: str):
    payments = get_cashfree_order_payments(cashfree_order_id)
    latest_payment = None
    for payment in payments:
        latest_payment = latest_payment or payment
        status = str(payment.get("payment_status") or "").strip().upper()
        if status == "SUCCESS":
            return True, payment
    return False, latest_payment
