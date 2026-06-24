"""Address parsing helpers for prospect records.

This module converts Google Places formatted addresses into sheet-friendly
address components. It exists so parsing stays isolated from pipeline
orchestration and row serialization.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

EMPTY_ADDRESS_PARTS = {
    "street": "",
    "city": "",
    "state": "",
    "zip": "",
}


def parse_address(address: str) -> dict[str, str]:
    """Parse a Google Places formatted address into street, city, state, and ZIP."""
    try:
        normalized = address.strip()
        if not normalized:
            raise ValueError("address is empty")

        if normalized.endswith(", USA"):
            normalized = normalized.removesuffix(", USA")

        parts = [part.strip() for part in normalized.split(",")]
        if len(parts) < 3:
            raise ValueError("address does not contain street, city, and state/ZIP")

        state_zip_match = re.fullmatch(r"([A-Z]{2})\s+(\d{5})", parts[2])
        if state_zip_match is None:
            raise ValueError("state and ZIP segment did not match expected format")

        return {
            "street": parts[0],
            "city": parts[1],
            "state": state_zip_match.group(1),
            "zip": state_zip_match.group(2),
        }
    except Exception as exc:
        logger.warning("Could not parse address '%s': %s", address, exc)
        return EMPTY_ADDRESS_PARTS.copy()
