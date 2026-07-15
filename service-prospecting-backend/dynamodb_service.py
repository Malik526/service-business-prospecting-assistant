"""DynamoDB persistence helpers for prospect records.

The backend stores prospects under a simple MVP key shape: `user_id` as the
partition key and `place_id` as the sort key. Numeric values are converted to
Decimal because boto3's DynamoDB resource API rejects native floats.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Key

from prospecting.config import load_config


CONFIG = load_config()
dynamodb = boto3.resource("dynamodb", region_name=CONFIG.aws_region)
prospects_table = dynamodb.Table(CONFIG.prospects_table_name)
usage_logs_table = dynamodb.Table(CONFIG.usage_logs_table_name)
search_history_table = dynamodb.Table(CONFIG.search_history_table_name)
feedback_table = dynamodb.Table(CONFIG.feedback_table_name)


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


def log_search(
    user_id: str,
    zip_code: str,
    radius: float,
    categories: str | None,
    prospect_count: int,
    search_id: str,
) -> None:
    """Write a non-critical search usage log and saved search history item."""
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        usage_logs_table.put_item(
            Item={
                "user_id": user_id,
                "timestamp": timestamp,
                "event_type": "search",
                "search_id": search_id,
                "zip_code": zip_code,
                "radius": _decimal_or_zero(radius),
                "categories": categories or "",
                "prospect_count": prospect_count,
                "date": timestamp[:10],
            }
        )
    except Exception as exc:
        print(f"Warning: could not write usage log: {exc}")

    try:
        search_history_table.put_item(
            Item={
                "user_id": user_id,
                "search_id": search_id,
                "created_at": timestamp,
                "zip_code": zip_code,
                "radius": _decimal_or_zero(radius),
                "categories": categories or "",
                "prospect_count": prospect_count,
            }
        )
    except Exception as exc:
        print(f"Warning: could not write search history: {exc}")


def log_feedback(user_id: str, feedback: str, source_path: str) -> str:
    """Store one feedback submission and return its generated ID."""
    feedback_id = str(uuid4())
    feedback_table.put_item(
        Item={
            "feedback_id": feedback_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "feedback": feedback,
            "source_path": source_path,
            "status": "new",
        }
    )
    return feedback_id


def get_usage_log_count(limit: int = 1000) -> int:
    """Return an approximate count of recent usage log records."""
    try:
        response = usage_logs_table.scan(Select="COUNT", Limit=limit)
        return int(response.get("Count", 0))
    except Exception as exc:
        print(f"Warning: could not scan usage logs: {exc}")
        return 0
