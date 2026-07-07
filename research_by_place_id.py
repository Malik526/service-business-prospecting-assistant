#!/usr/bin/env python3
"""Standalone research brief generator for a Google Place ID.

This script bypasses Google Sheets for quick one-off research runs. It fetches
Place Details directly from Google Places, formats those details like an
existing prospect row, runs the Claude research agent, and writes a clean brand
brief JSON file in the project root.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config import load_config
from google_places import GooglePlacesClient
from pipeline.output import sanitize_website_content
from pipeline.research import run_research_agent
from pipeline.utils import setup_logger


logger = setup_logger("research_by_place_id")
PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    """Parse the required Place ID argument."""
    parser = argparse.ArgumentParser(
        description="Generate a standalone research brief from a Google Place ID."
    )
    parser.add_argument(
        "place_id",
        help="Google Maps Place ID to fetch directly from Google Places.",
    )
    return parser.parse_args()


def validate_standalone_config() -> tuple[str, str]:
    """Load and validate only the API keys needed for standalone research."""
    config = load_config()
    missing: list[str] = []

    if not config.google_places_api_key:
        missing.append("GOOGLE_PLACES_API_KEY")
    if not config.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return config.google_places_api_key, config.anthropic_api_key


def fetch_place_details(place_id: str, api_key: str) -> dict[str, Any] | None:
    """Fetch Google Place Details for a single Place ID."""
    client = GooglePlacesClient(api_key=api_key, max_pages_per_category=1)

    try:
        logger.info("Fetching place details for: %s", place_id)
        details = client.get_place_details(place_id)
    except Exception as exc:
        logger.error("Error fetching place details: %s", exc)
        return None

    if not details:
        logger.error("No place details found for: %s", place_id)
        return None

    logger.info(
        "Found: %s - rating %s (%s reviews)",
        details.get("name", "Unknown"),
        details.get("rating", "N/A"),
        details.get("user_ratings_total", 0),
    )
    return details


def build_prospect_dict(place_details: dict[str, Any], place_id: str) -> dict[str, Any]:
    """Convert Place Details into the prospect shape expected by the research agent."""
    return {
        "Place ID": place_details.get("place_id") or place_id,
        "Business Name": place_details.get("name", "Unknown"),
        "Category": "Service Business",
        "Address": place_details.get("formatted_address", ""),
        "Phone": place_details.get("formatted_phone_number", ""),
        "Website": place_details.get("website", "") or "",
        "Google Maps URL": place_details.get("url", ""),
        "Rating": place_details.get("rating", "N/A"),
        "Review Count": place_details.get("user_ratings_total", 0),
        "Weighted Reputation Score": "N/A",
        "Why Good Fit": "Direct Place ID lookup",
        "Lead Score": "N/A",
    }


def extract_five_star_reviews(place_details: dict[str, Any]) -> list[dict[str, Any]]:
    """Return five-star reviews in the format consumed by the research prompt."""
    reviews = place_details.get("reviews", [])
    five_star_reviews = [
        {
            "author_name": review.get("author_name", "Anonymous"),
            "rating": review.get("rating"),
            "text": review.get("text", "").strip(),
            "relative_time_description": review.get("relative_time_description", ""),
        }
        for review in reviews
        if review.get("rating") == 5
    ]

    logger.info(
        "Found %d five-star review(s) out of %d returned review(s)",
        len(five_star_reviews),
        len(reviews),
    )
    return five_star_reviews


def run_research(
    place_id: str,
    google_api_key: str,
    anthropic_api_key: str,
) -> dict[str, Any] | None:
    """Fetch Place Details, build a prospect dict, and run the research agent."""
    place_details = fetch_place_details(place_id, google_api_key)
    if not place_details:
        return None

    prospect = build_prospect_dict(place_details, place_id)
    reviews = extract_five_star_reviews(place_details)

    logger.info("Running research agent for: %s", prospect.get("Business Name"))
    brief = run_research_agent(
        prospect=prospect,
        api_key=anthropic_api_key,
        reviews=reviews or None,
    )

    if not brief:
        logger.error("Research agent failed to produce a valid brief")
        return None

    logger.info("Research agent completed successfully")
    return sanitize_website_content(brief)


def build_output_path(place_id: str) -> Path:
    """Build a timestamped output path in the project root."""
    safe_place_id = re.sub(r"[^A-Za-z0-9_-]+", "-", place_id).strip("-")
    safe_place_id = safe_place_id[-16:] if safe_place_id else "place-id"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return PROJECT_ROOT / f"brief_{safe_place_id}_{timestamp}.json"


def save_brief(brief: dict[str, Any], place_id: str) -> Path:
    """Write the standalone brand brief JSON to disk."""
    output_path = build_output_path(place_id)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(brief, file, indent=2, ensure_ascii=False)
        file.write("\n")

    logger.info("Brief saved to: %s", output_path)
    return output_path


def print_quick_reference(brief: dict[str, Any], output_path: Path) -> None:
    """Print the full brief and key fields for terminal review."""
    print("\n" + "=" * 80)
    print("BRAND BRIEF")
    print("=" * 80)
    print(json.dumps(brief, indent=2, ensure_ascii=False))
    print("=" * 80)
    print(f"\nFull brief saved to: {output_path}")

    print("\n" + "-" * 80)
    print("QUICK REFERENCE")
    print("-" * 80)
    print(f"Brand Voice: {brief.get('brand_voice', 'N/A')}")
    print(f"Cold Call Hook: {brief.get('cold_call_hook', 'N/A')}")
    print(f"Review Themes: {', '.join(brief.get('review_themes', []))}")
    print(f"Key Services: {', '.join(brief.get('key_services', []))}")
    print(f"SEO Keywords: {', '.join(brief.get('seo_keywords', []))}")


def main() -> None:
    """Run the standalone Place ID research workflow."""
    args = parse_args()

    try:
        google_api_key, anthropic_api_key = validate_standalone_config()
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info("Starting standalone research for Place ID: %s", args.place_id)
    brief = run_research(args.place_id, google_api_key, anthropic_api_key)
    if not brief:
        logger.error("Research failed")
        sys.exit(1)

    output_path = save_brief(brief, args.place_id)
    print_quick_reference(brief, output_path)


if __name__ == "__main__":
    main()
