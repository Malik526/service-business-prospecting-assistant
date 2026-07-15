"""Search result preparation for the SaaS backend.

This module turns raw Google Places prospects into API-ready records by applying
deduplication, scoring, search metadata, address parsing, and stable defaults.
It stays separate from FastAPI so endpoint code remains thin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .dedupe import add_to_index, build_dedupe_index, is_duplicate
from .scoring import score_prospect, weighted_reputation_score, why_good_fit


def extract_address_components(address_components: list[dict[str, Any]]) -> dict[str, str]:
    """Extract Street, City, State, and ZIP fields from Google address components."""
    street_number = ""
    route = ""
    city = ""
    state = ""
    zip_code = ""

    for component in address_components or []:
        component_types = set(component.get("types", []))
        if "street_number" in component_types:
            street_number = component.get("long_name", "")
        elif "route" in component_types:
            route = component.get("long_name", "")
        elif "locality" in component_types:
            city = component.get("long_name", "")
        elif "administrative_area_level_1" in component_types:
            state = component.get("short_name", "") or component.get("long_name", "")
        elif "postal_code" in component_types:
            zip_code = component.get("long_name", "")

    return {
        "street": " ".join(part for part in (street_number, route) if part),
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def prepare_new_prospects(
    raw_prospects: list[dict[str, Any]],
    selected_categories: list[dict[str, Any]],
    existing_records: list[dict[str, Any]],
    search_zip: str,
    search_radius: float,
) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate and enrich Google Places prospects for API storage."""
    dedupe_index = build_dedupe_index(existing_records)
    category_lookup = {category["name"]: category for category in selected_categories}
    date_added = datetime.now(timezone.utc).date().isoformat()
    new_prospects: list[dict[str, Any]] = []
    duplicate_count = 0

    for prospect in raw_prospects:
        if is_duplicate(prospect, dedupe_index):
            duplicate_count += 1
            continue

        category = category_lookup.get(prospect.get("category"), selected_categories[0])
        parsed_address = extract_address_components(prospect.get("address_components", []))

        prospect["date_added"] = date_added
        prospect["search_zip"] = search_zip
        prospect["search_radius"] = search_radius
        prospect["street"] = parsed_address.get("street", "")
        prospect["city"] = parsed_address.get("city", "")
        prospect["state"] = parsed_address.get("state", "")
        prospect["zip"] = parsed_address.get("zip", "")
        prospect["lead_score"] = score_prospect(prospect, category)
        prospect["weighted_reputation_score"] = weighted_reputation_score(prospect)
        prospect["why_good_fit"] = why_good_fit(prospect, category)
        prospect["status"] = "New"
        prospect["last_contact_date"] = ""
        prospect["last_outcome"] = "Not Called Yet"
        prospect["notes"] = ""
        prospect.setdefault("email", "")
        prospect.setdefault("instagram_url", "")

        new_prospects.append(prospect)
        add_to_index(prospect, dedupe_index)

    new_prospects.sort(key=lambda item: item.get("lead_score", 0), reverse=True)
    return new_prospects, duplicate_count

