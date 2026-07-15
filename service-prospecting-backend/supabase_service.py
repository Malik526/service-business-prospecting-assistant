"""Supabase user, usage, and admin helpers for monetization.

The backend uses the Supabase service role key to read user profiles, enforce
search limits, and update subscription metadata after Stripe events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from supabase import Client, create_client

from prospecting.config import load_config


LIMITS_BY_TIER = {
    "free": 25,
    "starter": 250,
    "pro": 1000,
    "business": 5000,
}

CONFIG = load_config()
_client: Client | None = None


def is_supabase_configured() -> bool:
    """Return True when required Supabase backend credentials are available."""
    return bool(CONFIG.supabase_url and CONFIG.supabase_service_role_key)


def get_supabase_client() -> Client:
    """Return a cached Supabase client or raise a setup error."""
    global _client
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    if _client is None:
        _client = create_client(CONFIG.supabase_url, CONFIG.supabase_service_role_key)
    return _client


def get_user_profile(user_id: str) -> dict[str, Any]:
    """Fetch one monetization user profile from Supabase."""
    response = (
        get_supabase_client()
        .table("users")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    return response.data


def ensure_search_allowed(user_id: str) -> dict[str, Any] | None:
    """Check whether the user has remaining searches for the current plan."""
    if not user_id or user_id.startswith("guest-") or not is_supabase_configured():
        return None

    user = get_user_profile(user_id)
    tier = str(user.get("subscription_status") or "free").lower()
    limit = int(user.get("free_tier_searches_limit") or LIMITS_BY_TIER.get(tier, 25))
    used = int(user.get("free_tier_searches_used") or 0)

    if used >= limit:
        raise HTTPException(
            status_code=403,
            detail="Search limit reached. Upgrade your plan to continue searching.",
        )

    return user


def increment_search_usage(user_id: str, user: dict[str, Any] | None = None) -> None:
    """Increment a user's search counter after a successful search completes."""
    if not user_id or user_id.startswith("guest-") or not is_supabase_configured():
        return

    profile = user or get_user_profile(user_id)
    used = int(profile.get("free_tier_searches_used") or 0)
    updated = {
        "free_tier_searches_used": used + 1,
        "last_search_date": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    get_supabase_client().table("users").update(updated).eq("id", user_id).execute()


def update_stripe_customer_id(user_id: str, customer_id: str) -> None:
    """Attach a Stripe customer ID to a Supabase user profile."""
    get_supabase_client().table("users").update(
        {
            "stripe_customer_id": customer_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", user_id).execute()


def update_subscription_from_price(customer_id: str, subscription_id: str, price_id: str) -> None:
    """Update a user's subscription tier and monthly limit from a Stripe price ID."""
    tier = stripe_price_to_tier(price_id)
    get_supabase_client().table("users").update(
        {
            "subscription_status": tier,
            "stripe_subscription_id": subscription_id,
            "free_tier_searches_limit": LIMITS_BY_TIER[tier],
            "free_tier_searches_used": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("stripe_customer_id", customer_id).execute()


def downgrade_subscription(customer_id: str) -> None:
    """Downgrade a Stripe customer back to the free tier."""
    get_supabase_client().table("users").update(
        {
            "subscription_status": "free",
            "stripe_subscription_id": "",
            "free_tier_searches_limit": LIMITS_BY_TIER["free"],
            "free_tier_searches_used": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("stripe_customer_id", customer_id).execute()


def stripe_price_to_tier(price_id: str) -> str:
    """Map configured Stripe price IDs to subscription tier names."""
    price_map = {
        CONFIG.stripe_price_starter_monthly: "starter",
        CONFIG.stripe_price_pro_monthly: "pro",
        CONFIG.stripe_price_business_monthly: "business",
    }
    return price_map.get(price_id, "free")


def list_user_profiles() -> list[dict[str, Any]]:
    """Fetch user profiles for the admin dashboard."""
    response = get_supabase_client().table("users").select("*").execute()
    return list(response.data or [])
