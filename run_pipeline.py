"""Research pipeline orchestrator for the service business prospecting assistant.

Full pipeline flow
------------------
  Step 1/4: Fetch the business record from Google Sheets using a Place ID.
  Step 2/4: Run the Claude research agent to generate a structured brand brief.
  Step 3/4: Merge the prospect data and brand brief into a final brief object.
  Step 4/4: Write the brief to briefs/<slug>.json.

Required environment variables (.env file at this directory)
------------------------------------------------------------
  ANTHROPIC_API_KEY           → Anthropic API key for Claude access.
  GOOGLE_PLACES_API_KEY       → Google Places API key (used by main.py prospecting run).
  GOOGLE_SHEET_ID             → ID of the Google Sheet containing prospects.
  GOOGLE_SERVICE_ACCOUNT_FILE → Path to service account JSON key file.

How to run
----------
  python run_pipeline.py --place-id <PLACE_ID>
  python run_pipeline.py --place-id <PLACE_ID> --sheet-id <SHEET_ID>

Example (Glow Aesthetics & Med Spa NYC)
---------------------------------------
  python run_pipeline.py --place-id ChIJhVpybR5fwokRSgKTBw5tuUU

Notes
-----
  - The Place ID must already exist in the Google Sheet (added by main.py).
    If it is not found, the pipeline exits early with a clear message.
  - The --sheet-id flag overrides GOOGLE_SHEET_ID from the environment for
    this run only. Useful for testing against a staging sheet.
  - Output briefs are written to briefs/<slug>.json relative to this directory.
"""

from __future__ import annotations

import argparse
import sys

from config import load_config, validate_config
from google_places import GooglePlacesClient
from google_sheets import GoogleSheetsClient
from pipeline.output import write_brief
from pipeline.research import run_research_agent
from pipeline.utils import setup_logger

logger = setup_logger("run_pipeline")


def parse_args() -> argparse.Namespace:
    """Parse required and optional CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run the research pipeline for a single prospect by Place ID."
    )
    parser.add_argument(
        "--place-id",
        required=True,
        dest="place_id",
        help="Google Maps Place ID to look up in the sheet and research.",
    )
    parser.add_argument(
        "--sheet-id",
        required=False,
        dest="sheet_id",
        default=None,
        help="Override GOOGLE_SHEET_ID env var for this run.",
    )
    return parser.parse_args()


def print_brief_summary(brand_brief: dict) -> None:
    """Print a human-readable summary of the key brand brief fields to stdout.

    Shows brand_voice, headline_suggestion, cold_call_hook, and seo_keywords.
    Keeps output concise for quick review at the terminal.
    """
    sep = "-" * 52
    print(f"\n{sep}")
    print("  Brand Brief Summary")
    print(sep)

    print(f"\n  Brand Voice:")
    print(f"    {brand_brief.get('brand_voice', 'N/A')}")

    print(f"\n  Headline:")
    print(f"    {brand_brief.get('headline_suggestion', 'N/A')}")

    print(f"\n  Cold Call Hook:")
    print(f"    {brand_brief.get('cold_call_hook', 'N/A')}")

    keywords = brand_brief.get("seo_keywords", [])
    print(f"\n  SEO Keywords:")
    for kw in keywords:
        print(f"    • {kw}")

    print(f"\n{sep}\n")


def main() -> None:
    """Run the four-step research pipeline for a single prospect."""
    args = parse_args()

    # --- Load and validate config ---
    config = load_config()
    validate_config(config)

    # --sheet-id CLI flag overrides the env var for this run
    sheet_id = args.sheet_id if args.sheet_id else config.google_sheet_id

    # --- Step 1/4: Fetch business record from Google Sheets ---
    logger.info("Step 1/4: Fetching business record from Google Sheets...")
    sheets_client = GoogleSheetsClient(
        sheet_id=sheet_id,
        service_account_file=config.google_service_account_file,
        sheet_name=config.sheet_name,
    )

    prospect = sheets_client.get_record_by_place_id(args.place_id)

    if prospect is None:
        logger.error(
            "No record found for Place ID '%s'. "
            "Make sure you have run main.py first to populate the sheet, "
            "then verify the Place ID is correct.",
            args.place_id,
        )
        sys.exit(1)

    logger.info("Found: %s — %s", prospect.get("Business Name"), prospect.get("Address"))

    # --- Step 1b: Fetch real five-star reviews from Google Places API ---
    logger.info(
        "Step 1b/4: Fetching real five-star reviews from Google Places API..."
    )
    places_client = GooglePlacesClient(
        api_key=config.google_places_api_key,
        max_pages_per_category=1,
    )
    reviews = places_client.get_place_reviews(place_id=args.place_id)
    if reviews:
        logger.info(
            "Fetched %d five-star review(s) for: %s",
            len(reviews),
            prospect.get("Business Name"),
        )
    else:
        logger.warning(
            "No five-star reviews found for: %s — brief will use "
            "category-level assumptions only.",
            prospect.get("Business Name"),
        )

    # --- Step 2/4: Run Claude research agent ---
    logger.info("Step 2/4: Running business research agent (Claude API)...")
    brand_brief = run_research_agent(
        prospect,
        api_key=config.anthropic_api_key,
        reviews=reviews,
    )

    if brand_brief is None:
        logger.error(
            "Research agent failed to return a valid brief for '%s'. "
            "Check the Claude API response in the logs above.",
            prospect.get("Business Name"),
        )
        sys.exit(1)

    # --- Step 3/4: Build structured brief ---
    logger.info("Step 3/4: Building structured brief...")
    # write_brief() calls build_brief() internally; logged here for step visibility

    # --- Step 4/4: Write brief to disk ---
    from pipeline.utils import slugify
    slug = slugify(prospect.get("Business Name", "unknown"))
    logger.info("Step 4/4: Writing brief to briefs/%s.json", slug)

    output_path = write_brief(prospect, brand_brief)

    # --- Success output ---
    print(f"\n  Brief written to: {output_path}")
    print_brief_summary(brand_brief)


if __name__ == "__main__":
    main()
