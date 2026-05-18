"""Stripe payment helpers for SmartRetail."""

import os
from dotenv import load_dotenv
import stripe

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

if not STRIPE_SECRET_KEY:
    raise ValueError("❌ STRIPE_SECRET_KEY not found. Check your .env file")

stripe.api_key = STRIPE_SECRET_KEY

STRIPE_MIN_AMOUNT_INR = float(os.getenv("STRIPE_MIN_AMOUNT_INR", "50.0"))


def normalize_payment_method(payment_method: str) -> str:
    method = (payment_method or "").strip().lower()
    method_map = {
        "stripe_card": "card",
        "stripe_upi": "upi",
        "stripe_gpay": "gpay",
        "stripe_google_pay": "gpay",
        "stripe_wallet": "wallet",
        "stripe_netbanking": "netbanking",
        "card": "card",
        "upi": "upi",
        "gpay": "gpay",
        "wallet": "wallet",
        "netbanking": "netbanking",
    }
    return method_map.get(method, "card")


def stripe_payment_method_types(payment_method: str):
    normalized = normalize_payment_method(payment_method)
    # Note: Stripe Checkout exposes Google Pay via card wallet flows when eligible.
    mapping = {
        "card": ["card"],
        "upi": ["upi"],
        "gpay": ["card"],
        "wallet": ["card"],
        "netbanking": ["netbanking"],
    }
    return normalized, mapping.get(normalized, ["card"])


def create_stripe_checkout_session(amount, order_id, success_url, cancel_url, payment_method="card"):
    try:
        normalized_method, method_types = stripe_payment_method_types(payment_method)
        amount_inr = round(float(amount or 0.0), 2)

        if amount_inr <= 0:
            raise ValueError("Amount must be greater than zero")

        if amount_inr < STRIPE_MIN_AMOUNT_INR:
            raise ValueError(
                f"Amount must be at least INR {STRIPE_MIN_AMOUNT_INR:.2f} for Stripe checkout"
            )

        amount_paise = int(round(amount_inr * 100))

        print("👉 Stripe Payment Method:", normalized_method)
        print("👉 Amount:", amount_inr)
        print("👉 Amount in paise:", amount_paise)

        payload = {
            "mode": "payment",
            "payment_method_types": method_types,
            "line_items": [
                {
                    "price_data": {
                        "currency": "inr",
                        "product_data": {
                            "name": f"SmartRetail Order #{order_id}",
                        },
                        "unit_amount": amount_paise,
                    },
                    "quantity": 1,
                }
            ],
            "metadata": {
                "order_id": str(order_id),
                "selected_payment_method": normalized_method,
            },
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        session = stripe.checkout.Session.create(**payload)

        return {
            "id": session.id,
            "url": session.url
        }

    except Exception as e:
        print("🔥 STRIPE ERROR:", str(e))
        return None


def get_stripe_checkout_session(session_id):
    """
    Fetch Stripe Checkout Session details.
    """
    try:
        return stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        print(f"Error fetching Stripe checkout session: {e}")
        return None
