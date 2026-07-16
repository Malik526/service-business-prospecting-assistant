"""Shared utility helpers."""

from __future__ import annotations

import math
from datetime import date
from typing import Any


MILES_TO_METERS = 1609.344


def miles_to_meters(miles: float) -> int:
    """Convert miles to meters for Google Places radius parameters."""
    return round(miles * MILES_TO_METERS)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in miles between two lat/lng coordinates.

    Uses the Haversine formula, which accounts for Earth's spherical curvature.
    Accurate to within ~0.5% for distances under 100 miles — sufficient for
    local prospecting radii. Result is rounded to the nearest tenth of a mile.

    Args:
        lat1, lon1: Origin point (e.g., search ZIP centroid).
        lat2, lon2: Destination point (e.g., business location from Places API).
    """
    R = 3958.8  # Earth's mean radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


def clean_phone(phone: str | None) -> str:
    """Return only the numeric digits from a phone number."""
    if not phone:
        return ""
    return "".join(char for char in phone if char.isdigit())


def normalize_website(url: str | None) -> str:
    """Normalize website URLs for reliable deduplication."""
    if not url:
        return ""
    normalized = url.strip().lower()
    normalized = normalized.removeprefix("https://").removeprefix("http://")
    normalized = normalized.removeprefix("www.")
    return normalized.rstrip("/")


def normalize_text(value: str | None) -> str:
    """Normalize free-form text for exact and fuzzy matching."""
    if not value:
        return ""
    return " ".join(value.lower().strip().split())


def today_iso() -> str:
    """Return today's date in ISO-8601 format."""
    return date.today().isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    """Convert a value to int, returning a default on invalid input."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning a default on invalid input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
