"""Environment configuration for the FastAPI/Lambda prospecting backend.

The backend only requires the Google Places API key for searches and AWS
configuration for DynamoDB writes. Google Sheets and Anthropic settings remain
part of the local CLI and are intentionally not required here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class BackendConfig:
    """Typed backend settings loaded from environment variables."""

    google_places_api_key: str
    aws_region: str
    prospects_table_name: str
    users_table_name: str
    usage_logs_table_name: str
    search_history_table_name: str
    feedback_table_name: str
    max_pages_per_category: int
    supabase_url: str
    supabase_service_role_key: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    frontend_base_url: str
    admin_key: str
    stripe_price_starter_monthly: str
    stripe_price_pro_monthly: str
    stripe_price_business_monthly: str


def load_config() -> BackendConfig:
    """Load backend configuration from the current process environment."""
    return BackendConfig(
        google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY", "").strip(),
        aws_region=os.getenv("AWS_REGION", "us-east-1").strip() or "us-east-1",
        prospects_table_name=os.getenv("DYNAMODB_TABLE_PROSPECTS", "prospects").strip()
        or "prospects",
        users_table_name=os.getenv("DYNAMODB_TABLE_USERS", "users").strip() or "users",
        usage_logs_table_name=os.getenv("DYNAMODB_TABLE_USAGE_LOGS", "usage_logs").strip()
        or "usage_logs",
        search_history_table_name=os.getenv("DYNAMODB_TABLE_SEARCH_HISTORY", "search_history").strip()
        or "search_history",
        feedback_table_name=os.getenv("DYNAMODB_TABLE_FEEDBACK", "feedback").strip()
        or "feedback",
        max_pages_per_category=int(os.getenv("MAX_PAGES_PER_CATEGORY", "1")),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", "").strip(),
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", "").strip(),
        frontend_base_url=os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").strip()
        or "http://localhost:3000",
        admin_key=os.getenv("ADMIN_KEY", "").strip(),
        stripe_price_starter_monthly=os.getenv(
            "STRIPE_PRICE_STARTER_MONTHLY",
            "price_starter_monthly",
        ).strip(),
        stripe_price_pro_monthly=os.getenv("STRIPE_PRICE_PRO_MONTHLY", "price_pro_monthly").strip(),
        stripe_price_business_monthly=os.getenv(
            "STRIPE_PRICE_BUSINESS_MONTHLY",
            "price_business_monthly",
        ).strip(),
    )


def validate_config(config: BackendConfig) -> None:
    """Raise a clear error when required backend configuration is missing."""
    if not config.google_places_api_key:
        raise ValueError("Missing required environment variable: GOOGLE_PLACES_API_KEY")
