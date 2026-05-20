"""Shared utility helpers."""

from __future__ import annotations

from datetime import date
from typing import Any


MILES_TO_METERS = 1609.344


def miles_to_meters(miles: float) -> int:
    return round(miles * MILES_TO_METERS)


def clean_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return "".join(char for char in phone if char.isdigit())


def normalize_website(url: str | None) -> str:
    if not url:
        return ""
    normalized = url.strip().lower()
    normalized = normalized.removeprefix("https://").removeprefix("http://")
    normalized = normalized.removeprefix("www.")
    return normalized.rstrip("/")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().strip().split())


def today_iso() -> str:
    return date.today().isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
