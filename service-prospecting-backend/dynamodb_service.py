"""DynamoDB persistence helpers for prospect records.

The backend stores prospects under a simple MVP key shape: `user_id` as the
partition key and `place_id` as the sort key. Numeric values are converted to
Decimal because boto3's DynamoDB resource API rejects native floats.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from prospecting.config import load_config


CONFIG = load_config()
dynamodb = boto3.resource("dynamodb", region_name=CONFIG.aws_region)
prospects_table = dynamodb.Table(CONFIG.prospects_table_name)


def _decimal_or_zero(value: Any) -> Decimal:
    """Convert incoming numeric-like values to DynamoDB-safe Decimal values."""
    if value in (None, ""):
        return Decimal("0")

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _json_safe(value: Any) -> Any:
    """Convert DynamoDB Decimal values back into ordinary JSON primitives."""
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)

    if isinstance(value, dict):
        return {key: _json_safe(nested_value) for key, nested_value in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    return value


def store_prospect(user_id: str, prospect: dict[str, Any], search_id: str) -> None:
    """Store a single prospect record in DynamoDB."""
    place_id = str(prospect.get("place_id", "")).strip()
    if not place_id:
        raise ValueError("Cannot store prospect without a place_id")

    prospects_table.put_item(
        Item={
            "user_id": user_id,
            "place_id": place_id,
            "search_id": search_id,
            "business_name": prospect.get("business_name", ""),
            "category": prospect.get("category", ""),
            "address": prospect.get("address", ""),
            "phone": prospect.get("phone", ""),
            "website": prospect.get("website", ""),
            "google_maps_url": prospect.get("google_maps_url", ""),
            "rating": _decimal_or_zero(prospect.get("rating")),
            "review_count": int(_decimal_or_zero(prospect.get("review_count"))),
            "lead_score": _decimal_or_zero(prospect.get("lead_score")),
            "weighted_reputation_score": _decimal_or_zero(
                prospect.get("weighted_reputation_score")
            ),
            "distance_miles": _decimal_or_zero(prospect.get("distance_miles")),
            "email": prospect.get("email", ""),
            "instagram_url": prospect.get("instagram_url", ""),
            "why_good_fit": prospect.get("why_good_fit", ""),
            "status": prospect.get("status", "New"),
            "last_contact_date": prospect.get("last_contact_date", ""),
            "last_outcome": prospect.get("last_outcome", ""),
            "notes": prospect.get("notes", ""),
            "date_added": prospect.get("date_added", ""),
            "search_zip": prospect.get("search_zip", ""),
            "search_radius": _decimal_or_zero(prospect.get("search_radius")),
            "street": prospect.get("street", ""),
            "city": prospect.get("city", ""),
            "state": prospect.get("state", ""),
            "zip": prospect.get("zip", ""),
            "source": prospect.get("source", "Google Places API"),
        }
    )


def get_user_prospects(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve stored prospects for a single user."""
    response = prospects_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        Limit=limit,
    )
    return [_json_safe(item) for item in response.get("Items", [])]


def delete_prospect(user_id: str, place_id: str) -> None:
    """Delete one prospect by user ID and Google Place ID."""
    prospects_table.delete_item(Key={"user_id": user_id, "place_id": place_id})

