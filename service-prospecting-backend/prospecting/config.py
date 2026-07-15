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
    max_pages_per_category: int


def load_config() -> BackendConfig:
    """Load backend configuration from the current process environment."""
    return BackendConfig(
        google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY", "").strip(),
        aws_region=os.getenv("AWS_REGION", "us-east-1").strip() or "us-east-1",
        prospects_table_name=os.getenv("DYNAMODB_TABLE_PROSPECTS", "prospects").strip()
        or "prospects",
        users_table_name=os.getenv("DYNAMODB_TABLE_USERS", "users").strip() or "users",
        max_pages_per_category=int(os.getenv("MAX_PAGES_PER_CATEGORY", "1")),
    )


def validate_config(config: BackendConfig) -> None:
    """Raise a clear error when required backend configuration is missing."""
    if not config.google_places_api_key:
        raise ValueError("Missing required environment variable: GOOGLE_PLACES_API_KEY")

