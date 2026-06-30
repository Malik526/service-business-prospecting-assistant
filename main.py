"""CLI entrypoint and orchestration layer for the service business prospecting tool.

This module connects all components together:
  1. Parse CLI arguments (ZIP code, radius, optional categories).
  2. Load and validate environment configuration.
  3. Initialize Google Places and Google Sheets clients.
  4. Fetch existing records from the sheet for deduplication.
  5. Search Google Places for businesses across selected target categories.
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
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from categories import filter_target_categories

logger = logging.getLogger(__name__)
from config import load_config, validate_config
from dedupe import add_to_index, build_dedupe_index, is_duplicate
from google_places import GooglePlacesClient
from google_sheets import GoogleSheetsClient
from scoring import score_prospect, weighted_reputation_score, why_good_fit
from utils import safe_float, safe_int


REPORT_CATEGORIES = ("electrician", "hvac", "plumber")


def reporting_category(category: str) -> str | None:
    """Normalize internal category names into report-friendly keys."""
    normalized = category.strip().lower()
    if normalized in {"electrician", "electricians"}:
        return "electrician"
    if normalized == "hvac":
        return "hvac"
    if normalized in {"plumber", "plumbers"}:
        return "plumber"
    return None


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
    parser.add_argument(
        "--categories",
        help=(
            "Optional comma-separated category filter. "
            "Example: electrician,hvac,plumber. Defaults to all categories."
        ),
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Do not extract Email values from new prospect websites.",
    )
    parser.add_argument(
        "--skip-instagram",
        action="store_true",
        help="Do not extract Instagram URL values from new prospect websites.",
    )
    return parser.parse_args()


def selected_extractors(args: argparse.Namespace) -> list[str]:
    """Return contact extractors enabled by CLI flags."""
    extractors = []
    if not args.skip_email:
        extractors.append("email")
    if not args.skip_instagram:
        extractors.append("instagram_url")
    return extractors


def extract_address_components(address_components: list[dict[str, Any]]) -> dict[str, str]:
    """Extract Street, City, State, and ZIP from Google Places address components."""
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

    street = " ".join(part for part in (street_number, route) if part)
    return {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def enrich_with_score(prospect: dict[str, Any], category_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Add score, fit explanation, and default PROSPECTS fields to a prospect.

    Mutates and returns the same dict. Called after deduplication so only
    new prospects are scored (avoids wasting compute on duplicates).
    """
    category = category_lookup[prospect["category"]]
    prospect["lead_score"] = score_prospect(prospect, category)
    prospect["weighted_reputation_score"] = weighted_reputation_score(prospect)
    prospect["why_good_fit"] = why_good_fit(prospect, category)
    prospect["status"] = "New"
    prospect["last_contact_date"] = ""
    prospect["last_outcome"] = ""
    prospect["notes"] = ""
    return prospect


def print_summary(
    zip_code: str,
    radius: float,
    found_count: int,
    duplicate_count: int,
    added: list[dict[str, Any]],
    enabled_extractors: list[str],
    appended_count: int | None = None,
    append_skipped_duplicates: int = 0,
    extraction_stats: dict[str, int | float] | None = None,
) -> None:
    """Print a structured console report after a prospecting run.

    Covers:
      - Run parameters (ZIP, radius)
      - Counts (found, duplicates skipped, new records added)
      - Website coverage breakdown
      - Contact data extraction results (emails, Instagram URLs)
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
    print(f"  New businesses added:   {appended_count if appended_count is not None else len(added)}")
    if append_skipped_duplicates:
        print(f"  Append-time duplicates: {append_skipped_duplicates}")

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

    # --- Contact data extraction results ---
    sites_total = len(with_website)
    emails_found = sum(1 for p in with_website if p.get("email"))
    instagram_found = sum(1 for p in with_website if p.get("instagram_url"))

    print(f"\n{sep}")
    print("  Contact Data Extraction")
    print(sep)
    print(f"  Email extractor:     {'enabled' if 'email' in enabled_extractors else 'disabled'}")
    print(f"  Instagram extractor: {'enabled' if 'instagram_url' in enabled_extractors else 'disabled'}")
    print(f"  Emails found:    {emails_found:>4} / {sites_total} prospects with websites")
    print(f"  Instagram URLs:  {instagram_found:>4} / {sites_total} prospects with websites")
    if extraction_stats and "email" in enabled_extractors:
        print(f"  Emails accepted: {extraction_stats.get('emails_validated', 0):>4}")
        print(f"  Emails rejected: {extraction_stats.get('emails_rejected', 0):>4}")
        print(f"  Fake email rate: {extraction_stats.get('fake_email_rate', 0):>4}%")

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


def print_scraping_summary(
    new_prospects: list[dict[str, Any]],
    extraction_stats: dict[str, int | float] | None = None,
) -> None:
    """Emit machine-readable scraping stats for the parallel launcher."""
    category_counts = dict.fromkeys(REPORT_CATEGORIES, 0)
    emails_by_category = dict.fromkeys(REPORT_CATEGORIES, 0)
    instagrams_by_category = dict.fromkeys(REPORT_CATEGORIES, 0)
    emails_found = 0
    instagrams_found = 0

    for prospect in new_prospects:
        category = reporting_category(str(prospect.get("category", "")))
        if category:
            category_counts[category] += 1

        if str(prospect.get("email", "")).strip():
            emails_found += 1
            if category:
                emails_by_category[category] += 1

        if str(prospect.get("instagram_url", "")).strip():
            instagrams_found += 1
            if category:
                instagrams_by_category[category] += 1

    total = len(new_prospects)
    summary = {
        "total_prospects": total,
        "by_category": category_counts,
        "emails_found": emails_found,
        "emails_by_category": emails_by_category,
        "emails_captured_percent": round((emails_found / total * 100), 1) if total else 0,
        "instagrams_found": instagrams_found,
        "instagrams_by_category": instagrams_by_category,
        "instagrams_captured_percent": round((instagrams_found / total * 100), 1) if total else 0,
    }
    if extraction_stats:
        summary.update(
            {
                "emails_validated": extraction_stats.get("emails_validated", 0),
                "emails_rejected": extraction_stats.get("emails_rejected", 0),
                "fake_email_rate": extraction_stats.get("fake_email_rate", 0),
            }
        )

    print("SCRAPING_STATS:" + json.dumps(summary, sort_keys=True), file=sys.stderr)


def main() -> None:
    args = parse_args()
    config = load_config()
    validate_config(config)
    enabled_extractors = selected_extractors(args)
    try:
        selected_categories = filter_target_categories(args.categories)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc

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
    category_lookup = {category["name"]: category for category in selected_categories}

    # Discover raw prospects from Google Places across the selected categories.
    prospects = places_client.discover_prospects(
        categories=selected_categories,
        zip_code=args.zip_code,
        radius_miles=args.radius,
    )

    # Deduplicate, score, and collect new records.
    new_prospects = []
    duplicate_count = 0
    date_added = datetime.today().strftime("%Y-%m-%d")
    print(f"Adding date_added field to prospects: {date_added}")
    for prospect in prospects:
        if is_duplicate(prospect, dedupe_index):
            duplicate_count += 1
            continue

        # Tag each prospect with the run parameters for traceability.
        # Allows filtering and grouping by ZIP code and radius in the sheet.
        prospect["date_added"] = date_added
        prospect["search_zip"] = args.zip_code
        prospect["search_radius"] = args.radius

        # Split Google Places address_components into filterable sheet columns.
        parsed_address = extract_address_components(prospect.get("address_components", []))
        prospect["street"] = parsed_address.get("street", "")
        prospect["city"] = parsed_address.get("city", "")
        prospect["state"] = parsed_address.get("state", "")
        prospect["zip"] = parsed_address.get("zip", "")

        enriched = enrich_with_score(prospect, category_lookup)

        new_prospects.append(enriched)
        # Update index in-memory so later prospects in this run are checked
        # against prospects already accepted earlier in the same batch.
        add_to_index(enriched, dedupe_index)

    # --- Parallel contact-data extraction ---
    # Enabled extractors are fetched concurrently with a hard 3-minute ceiling
    # so the pipeline never hangs regardless of site responsiveness.
    prospects_with_sites = [p for p in new_prospects if p.get("website")]

    if prospects_with_sites and enabled_extractors:
        from pipeline.email_validation import reset_email_validation_stats

        reset_email_validation_stats()
        logger.info(
            "Extracting contact data for %d prospects...",
            len(prospects_with_sites),
        )

        EXTRACTION_TIMEOUT = 180  # Hard ceiling — never run longer than 3 minutes total
        start_time = time.time()

        def enrich_prospect(prospect: dict[str, Any]) -> dict[str, Any]:
            """Fetch enabled contact fields for a single prospect."""
            from pipeline.social import extract_email, extract_instagram_url

            website = prospect.get("website", "")
            if "email" in enabled_extractors:
                prospect["email"] = extract_email(website)
            if "instagram_url" in enabled_extractors:
                prospect["instagram_url"] = extract_instagram_url(website)
            return prospect

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(enrich_prospect, p): p for p in prospects_with_sites}

            for future in as_completed(futures, timeout=EXTRACTION_TIMEOUT):
                if time.time() - start_time > EXTRACTION_TIMEOUT:
                    logger.warning(
                        "Extraction time limit reached — stopping early with partial results"
                    )
                    executor.shutdown(wait=False)
                    break
                try:
                    future.result()
                except Exception as exc:
                    logger.warning("Enrichment failed: %s", exc)

        emails_found = sum(1 for p in prospects_with_sites if p.get("email"))
        instagram_found = sum(1 for p in prospects_with_sites if p.get("instagram_url"))
        logger.info(
            "Extraction complete — emails: %d, instagram: %d",
            emails_found,
            instagram_found,
        )
    elif prospects_with_sites:
        logger.info("Contact extraction skipped by CLI flags.")

    # Ensure every prospect has both keys so sheet row serialization is safe.
    for p in new_prospects:
        if "email" not in p:
            p["email"] = ""
        if "instagram_url" not in p:
            p["instagram_url"] = ""

    if "email" in enabled_extractors:
        from pipeline.email_validation import get_email_validation_stats

        extraction_stats = get_email_validation_stats()
    else:
        extraction_stats = None

    append_result = sheets_client.append_prospects(new_prospects)
    print_summary(
        args.zip_code,
        args.radius,
        len(prospects),
        duplicate_count,
        new_prospects,
        enabled_extractors=enabled_extractors,
        appended_count=append_result["appended"],
        append_skipped_duplicates=append_result["skipped_duplicates"],
        extraction_stats=extraction_stats,
    )
    print_scraping_summary(new_prospects, extraction_stats=extraction_stats)


if __name__ == "__main__":
    main()
