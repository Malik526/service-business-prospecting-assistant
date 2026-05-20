"""CLI entrypoint for service business prospecting."""

from __future__ import annotations

import argparse
from typing import Any

from categories import TARGET_CATEGORIES
from config import load_config, validate_config
from dedupe import add_to_index, build_dedupe_index, is_duplicate
from google_places import GooglePlacesClient
from google_sheets import GoogleSheetsClient
from scoring import score_prospect, why_good_fit
from utils import today_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find, dedupe, score, and store local service business prospects."
    )
    parser.add_argument("--zip", required=True, dest="zip_code", help="US ZIP code to search around.")
    parser.add_argument(
        "--radius",
        required=True,
        type=float,
        help="Search radius in miles. Example: 10, 20, 30.",
    )
    return parser.parse_args()


def enrich_with_score(prospect: dict[str, Any], category_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    category = category_lookup[prospect["category"]]
    prospect["lead_score"] = score_prospect(prospect, category)
    prospect["why_good_fit"] = why_good_fit(prospect, category)
    prospect["status"] = "New"
    prospect["date_added"] = today_iso()
    prospect["notes"] = ""
    return prospect


def print_summary(found_count: int, duplicate_count: int, added: list[dict[str, Any]]) -> None:
    print("\nProspecting run complete")
    print(f"Businesses found: {found_count}")
    print(f"Duplicates skipped: {duplicate_count}")
    print(f"New businesses added: {len(added)}")

    if not added:
        return

    print("\nTop 10 highest-scored prospects")
    top_prospects = sorted(added, key=lambda row: row.get("lead_score", 0), reverse=True)[:10]
    for index, prospect in enumerate(top_prospects, start=1):
        print(
            f"{index}. {prospect['business_name']} | "
            f"{prospect['category']} | "
            f"Score: {prospect['lead_score']} | "
            f"{prospect.get('phone') or 'No phone'} | "
            f"{prospect.get('website') or 'No website'}"
        )


def main() -> None:
    args = parse_args()
    config = load_config()
    validate_config(config)

    places_client = GooglePlacesClient(
        api_key=config.google_places_api_key,
        max_pages_per_category=config.max_pages_per_category,
    )
    sheets_client = GoogleSheetsClient(
        sheet_id=config.google_sheet_id,
        service_account_file=config.google_service_account_file,
        sheet_name=config.sheet_name,
    )

    existing_records = sheets_client.get_existing_records()
    dedupe_index = build_dedupe_index(existing_records)
    category_lookup = {category["name"]: category for category in TARGET_CATEGORIES}

    prospects = places_client.discover_prospects(
        categories=TARGET_CATEGORIES,
        zip_code=args.zip_code,
        radius_miles=args.radius,
    )

    new_prospects = []
    duplicate_count = 0
    for prospect in prospects:
        if is_duplicate(prospect, dedupe_index):
            duplicate_count += 1
            continue

        enriched = enrich_with_score(prospect, category_lookup)
        new_prospects.append(enriched)
        add_to_index(enriched, dedupe_index)

    sheets_client.append_prospects(new_prospects)
    print_summary(len(prospects), duplicate_count, new_prospects)


if __name__ == "__main__":
    main()
