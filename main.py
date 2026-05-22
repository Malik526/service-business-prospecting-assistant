"""CLI entrypoint and orchestration layer for the service business prospecting tool.

This module connects all components together:
  1. Parse CLI arguments (ZIP code, radius).
  2. Load and validate environment configuration.
  3. Initialize Google Places and Google Sheets clients.
  4. Fetch existing records from the sheet for deduplication.
  5. Search Google Places for businesses across all target categories.
  6. Deduplicate results against existing records (and within the current run).
  7. Score and enrich each new prospect.
  8. Append new prospects to the Google Sheet.
  9. Print a summary report to the console.

Responsibilities deliberately kept out of this module:
  - API communication (google_places.py)
  - Sheet read/write (google_sheets.py)
  - Deduplication logic (dedupe.py)
  - Scoring logic (scoring.py)
  - Category definitions (categories.py)
"""

from __future__ import annotations

import argparse
from typing import Any

from categories import TARGET_CATEGORIES
from config import load_config, validate_config
from dedupe import add_to_index, build_dedupe_index, is_duplicate
from google_places import GooglePlacesClient
from google_sheets import GoogleSheetsClient
from scoring import score_prospect, weighted_reputation_score, why_good_fit
from utils import safe_float, safe_int, today_iso


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
    """Add lead score, fit explanation, CRM status, and date to a prospect dict.

    Mutates and returns the same dict. Called after deduplication so only
    new prospects are scored (avoids wasting compute on duplicates).
    """
    category = category_lookup[prospect["category"]]
    prospect["lead_score"] = score_prospect(prospect, category)
    prospect["weighted_reputation_score"] = weighted_reputation_score(prospect)
    prospect["why_good_fit"] = why_good_fit(prospect, category)
    prospect["status"] = "New"
    prospect["date_added"] = today_iso()
    prospect["notes"] = ""
    return prospect


def print_summary(
    zip_code: str,
    radius: float,
    found_count: int,
    duplicate_count: int,
    added: list[dict[str, Any]],
) -> None:
    """Print a structured console report after a prospecting run.

    Covers:
      - Run parameters (ZIP, radius)
      - Counts (found, duplicates skipped, new records added)
      - Website coverage breakdown
      - Lead score distribution (average, range)
      - Closest businesses by distance
      - Highest review count businesses
      - Top businesses by Weighted Reputation Score
      - Top 10 highest-scored new prospects
    """
    sep = "-" * 52

    print(f"\n{'=' * 52}")
    print("  Prospecting Run Complete")
    print(f"{'=' * 52}")
    print(f"  ZIP:     {zip_code}")
    print(f"  Radius:  {radius:.0f} miles")

    print(f"\n{sep}")
    print("  Results")
    print(sep)
    print(f"  Businesses found:       {found_count}")
    print(f"  Duplicates skipped:     {duplicate_count}")
    print(f"  New businesses added:   {len(added)}")

    if not added:
        print(f"\n  No new prospects to report.")
        print(f"{'=' * 52}\n")
        return

    # --- Website coverage ---
    with_website = [p for p in added if p.get("website")]
    without_website = [p for p in added if not p.get("website")]
    total = len(added)
    pct_with = (len(with_website) / total * 100) if total else 0
    pct_without = (len(without_website) / total * 100) if total else 0

    print(f"\n{sep}")
    print("  Website Coverage")
    print(sep)
    print(f"  With website:    {len(with_website):>4}  ({pct_with:.1f}%)")
    print(f"  No website:      {len(without_website):>4}  ({pct_without:.1f}%)")

    # --- Lead score stats ---
    scores = [safe_int(p.get("lead_score", 0)) for p in added]
    avg_score = sum(scores) / len(scores) if scores else 0
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0

    print(f"\n{sep}")
    print("  Lead Score Distribution")
    print(sep)
    print(f"  Average:         {avg_score:.1f}")
    print(f"  Range:           {min_score} – {max_score}")

    # --- Closest by distance ---
    # Filter to prospects that have a numeric distance (not "") before sorting.
    with_distance = [p for p in added if isinstance(p.get("distance_miles"), (int, float))]
    if with_distance:
        closest = sorted(with_distance, key=lambda p: safe_float(p.get("distance_miles", 99999)))[:5]
        print(f"\n{sep}")
        print("  5 Closest Businesses")
        print(sep)
        for i, p in enumerate(closest, 1):
            print(
                f"  {i}. {p['business_name']:<30} "
                f"{p.get('distance_miles')} mi | "
                f"{p['category']} | "
                f"Score {p.get('lead_score', '—')}"
            )

    # --- Highest review counts ---
    with_reviews = [p for p in added if safe_int(p.get("review_count")) > 0]
    if with_reviews:
        top_reviewed = sorted(with_reviews, key=lambda p: safe_int(p.get("review_count", 0)), reverse=True)[:5]
        print(f"\n{sep}")
        print("  5 Most-Reviewed Businesses")
        print(sep)
        for i, p in enumerate(top_reviewed, 1):
            print(
                f"  {i}. {p['business_name']:<30} "
                f"{p.get('review_count')} reviews | "
                f"{p['category']} | "
                f"Score {p.get('lead_score', '—')}"
            )

    # --- Weighted Reputation Score ---
    with_weighted_reputation = [
        p for p in added if isinstance(p.get("weighted_reputation_score"), (int, float))
    ]
    if with_weighted_reputation:
        top_reputation = sorted(
            with_weighted_reputation,
            key=lambda p: safe_float(p.get("weighted_reputation_score", 0)),
            reverse=True,
        )[:5]
        print(f"\n{sep}")
        print("  5 Highest Weighted Reputation Scores")
        print(sep)
        for i, p in enumerate(top_reputation, 1):
            print(
                f"  {i}. {p['business_name']:<30} "
                f"WRS {p.get('weighted_reputation_score')} | "
                f"{p.get('rating', '—')} stars | "
                f"{p.get('review_count', '—')} reviews"
            )

    # --- Top scored prospects ---
    top_prospects = sorted(added, key=lambda p: safe_int(p.get("lead_score", 0)), reverse=True)[:10]
    print(f"\n{sep}")
    print("  Top 10 by Lead Score")
    print(sep)
    for i, p in enumerate(top_prospects, 1):
        phone_display = p.get("phone") or "No phone"
        website_display = p.get("website") or "No website"
        print(
            f"  {i:>2}. {p['business_name']:<28} "
            f"Score {p.get('lead_score', '—')} | "
            f"{p['category']} | "
            f"{phone_display} | "
            f"{website_display}"
        )

    print(f"{'=' * 52}\n")


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

    # Load existing sheet records to build the dedupe index.
    existing_records = sheets_client.get_existing_records()
    dedupe_index = build_dedupe_index(existing_records)
    category_lookup = {category["name"]: category for category in TARGET_CATEGORIES}

    # Discover raw prospects from Google Places across all categories.
    prospects = places_client.discover_prospects(
        categories=TARGET_CATEGORIES,
        zip_code=args.zip_code,
        radius_miles=args.radius,
    )

    # Deduplicate, score, and collect new records.
    new_prospects = []
    duplicate_count = 0
    for prospect in prospects:
        if is_duplicate(prospect, dedupe_index):
            duplicate_count += 1
            continue

        # Tag each prospect with the run parameters for traceability.
        # Allows filtering and grouping by ZIP code and radius in the sheet.
        prospect["search_zip"] = args.zip_code
        prospect["search_radius"] = args.radius

        enriched = enrich_with_score(prospect, category_lookup)
        new_prospects.append(enriched)
        # Update index in-memory so later prospects in this run are checked
        # against prospects already accepted earlier in the same batch.
        add_to_index(enriched, dedupe_index)

    sheets_client.append_prospects(new_prospects)
    print_summary(args.zip_code, args.radius, len(prospects), duplicate_count, new_prospects)


if __name__ == "__main__":
    main()
