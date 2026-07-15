"""Stripe checkout, billing portal, and webhook helpers.

The FastAPI routes call this module so billing logic stays isolated from the
prospecting search endpoint.
"""

from __future__ import annotations

from typing import Any

import stripe
from fastapi import HTTPException

from prospecting.config import load_config
from supabase_service import (
    downgrade_subscription,
    get_user_profile,
    update_stripe_customer_id,
    update_subscription_from_price,
)


CONFIG = load_config()
stripe.api_key = CONFIG.stripe_secret_key


def _require_stripe() -> None:
    """Raise a setup error when Stripe credentials are missing."""
    if not CONFIG.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")


def create_checkout_session(user_id: str, price_id: str) -> dict[str, str]:
    """Create a Stripe Checkout subscription session for a user and price."""
    _require_stripe()
    if not user_id or not price_id:
        raise HTTPException(status_code=400, detail="user_id and price_id are required")
    if price_id not in _allowed_price_ids():
        raise HTTPException(status_code=400, detail="Unknown Stripe price ID")

    user = get_user_profile(user_id)
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(email=user.get("email"), metadata={"user_id": user_id})
        customer_id = customer.id
        update_stripe_customer_id(user_id, customer_id)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{CONFIG.frontend_base_url}/upgrade-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{CONFIG.frontend_base_url}/upgrade-canceled",
    )
    return {"session_id": session.id, "checkout_url": session.url}


def create_billing_portal_session(user_id: str) -> dict[str, str]:
    """Create a Stripe Billing Portal session for an existing customer."""
    _require_stripe()
    user = get_user_profile(user_id)
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="No billing profile found")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{CONFIG.frontend_base_url}/prospecting",
    )
    return {"portal_url": session.url}


def _allowed_price_ids() -> set[str]:
    """Return the configured Stripe subscription price IDs."""
    return {
        CONFIG.stripe_price_starter_monthly,
        CONFIG.stripe_price_pro_monthly,
        CONFIG.stripe_price_business_monthly,
    }


def parse_webhook_event(payload: bytes, signature: str | None) -> Any:
    """Validate and parse a Stripe webhook event payload."""
    _require_stripe()
    if not CONFIG.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")

    try:
        return stripe.Webhook.construct_event(payload, signature, CONFIG.stripe_webhook_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe payload") from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc


def handle_subscription_event(event: Any) -> None:
    """Apply subscription lifecycle changes from Stripe webhooks."""
    event_type = event.get("type")
    subscription = event.get("data", {}).get("object", {})
    customer_id = subscription.get("customer", "")

    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        subscription_id = subscription.get("id", "")
        items = subscription.get("items", {}).get("data", [])
        price_id = items[0].get("price", {}).get("id", "") if items else ""
        update_subscription_from_price(customer_id, subscription_id, price_id)

    if event_type == "customer.subscription.deleted":
        downgrade_subscription(customer_id)
