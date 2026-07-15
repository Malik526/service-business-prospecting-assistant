"""FastAPI application for the Service Prospecting SaaS backend.

The app exposes a single-search MVP API: users submit a ZIP code, radius, and
optional category list; the backend queries Google Places, dedupes results for
that user, scores prospects, stores them in DynamoDB, and returns JSON.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dynamodb_service import (
    delete_prospect,
    get_usage_log_count,
    get_user_prospects,
    log_feedback,
    log_search,
    store_prospect,
)
from prospecting.categories import filter_target_categories
from prospecting.config import load_config, validate_config
from prospecting.google_places import GooglePlacesClient
from prospecting.search import prepare_new_prospects
from stripe_service import (
    create_billing_portal_session,
    create_checkout_session,
    handle_subscription_event,
    parse_webhook_event,
)
from supabase_service import ensure_search_allowed, increment_search_usage, list_user_profiles


app = FastAPI(title="Service Prospecting API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    """Request body for a single prospect search."""

    zip_code: str = Field(..., min_length=5, max_length=10)
    radius: float = Field(20, gt=0, le=100)
    categories: str | None = None
    user_id: str | None = None


class ProspectResponse(BaseModel):
    """Prospect fields returned to the frontend results table."""

    place_id: str
    business_name: str
    category: str
    rating: float
    review_count: int
    lead_score: float
    weighted_reputation_score: float
    address: str
    phone: str
    website: str
    google_maps_url: str
    distance_miles: float
    email: str = ""
    instagram_url: str = ""


class SearchResponse(BaseModel):
    """Response body returned after a prospect search completes."""

    count: int
    duplicate_count: int
    prospects: list[ProspectResponse]
    search_id: str
    user_id: str


class CheckoutSessionRequest(BaseModel):
    """Request body for Stripe Checkout session creation."""

    user_id: str
    price_id: str


class BillingPortalRequest(BaseModel):
    """Request body for Stripe Billing Portal session creation."""

    user_id: str


class FeedbackRequest(BaseModel):
    """Request body for product feedback submissions."""

    user_id: str = ""
    feedback: str = Field(..., min_length=3, max_length=4000)
    source_path: str = "/feedback"


class AdminStatsResponse(BaseModel):
    """Admin dashboard metrics returned by the backend."""

    total_users: int
    free_users: int
    paid_users: int
    total_searches: int
    total_revenue: int = 0


def _float_value(value: Any) -> float:
    """Convert optional numeric values into response-safe floats."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_value(value: Any) -> int:
    """Convert optional numeric values into response-safe integers."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_response(prospect: dict[str, Any]) -> ProspectResponse:
    """Map an internal prospect dict into the public response model."""
    return ProspectResponse(
        place_id=prospect.get("place_id", ""),
        business_name=prospect.get("business_name", ""),
        category=prospect.get("category", ""),
        rating=_float_value(prospect.get("rating")),
        review_count=_int_value(prospect.get("review_count")),
        lead_score=_float_value(prospect.get("lead_score")),
        weighted_reputation_score=_float_value(prospect.get("weighted_reputation_score")),
        address=prospect.get("address", ""),
        phone=prospect.get("phone", ""),
        website=prospect.get("website", ""),
        google_maps_url=prospect.get("google_maps_url", ""),
        distance_miles=_float_value(prospect.get("distance_miles")),
        email=prospect.get("email", ""),
        instagram_url=prospect.get("instagram_url", ""),
    )


@app.post("/api/prospects", response_model=SearchResponse)
async def search_prospects(request: SearchRequest) -> SearchResponse:
    """Search Google Places for prospects and store new records in DynamoDB."""
    try:
        config = load_config()
        validate_config(config)
        selected_categories = filter_target_categories(request.categories)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_id = request.user_id or f"guest-{uuid.uuid4()}"
    search_id = str(uuid.uuid4())

    try:
        user_profile = ensure_search_allowed(user_id)
        places_client = GooglePlacesClient(
            api_key=config.google_places_api_key,
            max_pages_per_category=config.max_pages_per_category,
        )
        raw_prospects = places_client.discover_prospects(
            categories=selected_categories,
            zip_code=request.zip_code,
            radius_miles=request.radius,
        )
        existing_records = get_user_prospects(user_id, limit=1000)
        new_prospects, duplicate_count = prepare_new_prospects(
            raw_prospects=raw_prospects,
            selected_categories=selected_categories,
            existing_records=existing_records,
            search_zip=request.zip_code,
            search_radius=request.radius,
        )

        for prospect in new_prospects:
            store_prospect(user_id=user_id, prospect=prospect, search_id=search_id)

        increment_search_usage(user_id, user_profile)
        log_search(
            user_id=user_id,
            zip_code=request.zip_code,
            radius=request.radius,
            categories=request.categories,
            prospect_count=len(new_prospects),
            search_id=search_id,
        )

        return SearchResponse(
            count=len(new_prospects),
            duplicate_count=duplicate_count,
            prospects=[_to_response(prospect) for prospect in new_prospects],
            search_id=search_id,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@app.post("/api/create-checkout-session")
async def create_checkout_session_endpoint(request: CheckoutSessionRequest) -> dict[str, str]:
    """Create a Stripe Checkout session for a subscription upgrade."""
    return create_checkout_session(user_id=request.user_id, price_id=request.price_id)


@app.post("/api/billing-portal")
async def create_billing_portal_endpoint(request: BillingPortalRequest) -> dict[str, str]:
    """Create a Stripe Billing Portal session for subscription management."""
    return create_billing_portal_session(user_id=request.user_id)


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle Stripe subscription lifecycle webhook events."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    event = parse_webhook_event(payload, signature)
    handle_subscription_event(event)
    return {"status": "success"}


@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest) -> dict[str, str]:
    """Store product feedback for weekly review."""
    feedback_id = log_feedback(
        user_id=request.user_id,
        feedback=request.feedback,
        source_path=request.source_path,
    )
    return {"status": "received", "feedback_id": feedback_id}


@app.get("/api/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(admin_key: str) -> AdminStatsResponse:
    """Return high-level SaaS metrics for the admin dashboard."""
    config = load_config()
    if not config.admin_key or admin_key != config.admin_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    users = list_user_profiles()
    free_users = [
        user for user in users if str(user.get("subscription_status", "free")).lower() == "free"
    ]
    paid_users = len(users) - len(free_users)

    return AdminStatsResponse(
        total_users=len(users),
        free_users=len(free_users),
        paid_users=paid_users,
        total_searches=get_usage_log_count(),
        total_revenue=0,
    )


@app.get("/api/prospects/{user_id}")
async def get_prospects(user_id: str, limit: int = 100) -> dict[str, Any]:
    """Return stored prospects for a user."""
    try:
        prospects = get_user_prospects(user_id, limit)
        return {"count": len(prospects), "prospects": prospects}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}") from exc


@app.delete("/api/prospects/{user_id}/{place_id}")
async def delete_prospect_endpoint(user_id: str, place_id: str) -> dict[str, str]:
    """Delete a stored prospect for a user."""
    try:
        delete_prospect(user_id, place_id)
        return {"message": "Prospect deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {exc}") from exc


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a lightweight health check response."""
    return {"status": "ok", "service": "prospecting-api"}


@app.get("/")
async def root() -> dict[str, str]:
    """Return a small root response for manual smoke checks."""
    return {"message": "Service Prospecting API", "docs": "/docs"}
