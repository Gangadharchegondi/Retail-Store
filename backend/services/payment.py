"""Payment helpers for SmartRetail (Cashfree/COD)."""

import os


CHECKOUT_MIN_AMOUNT_INR = float(os.getenv("CHECKOUT_MIN_AMOUNT_INR", "0.0"))
CASHFREE_PROVIDER_MIN_AMOUNT_INR = float(os.getenv("CASHFREE_MIN_AMOUNT_INR", "1.0"))


def normalize_payment_method(payment_method: str) -> str:
    method = (payment_method or "").strip().lower()
    method_map = {
        "cashfree_card": "card",
        "cashfree_upi": "upi",
        "cashfree_gpay": "gpay",
        "cashfree_wallet": "wallet",
        "cashfree_netbanking": "netbanking",
        # Standard method names.
        "card": "card",
        "upi": "upi",
        "gpay": "gpay",
        "wallet": "wallet",
        "netbanking": "netbanking",
        "cash": "cash",
        "cod": "cash",
        "cash_on_delivery": "cash",
    }
    return method_map.get(method, "card")


def gateway_checkout_minimum_inr(payment_method: str = "card") -> float:
    normalized = normalize_payment_method(payment_method)
    if normalized == "cash":
        return 0.0

    # Keep provider floor and allow env-based overrides above that.
    return max(0.0, CHECKOUT_MIN_AMOUNT_INR, CASHFREE_PROVIDER_MIN_AMOUNT_INR)