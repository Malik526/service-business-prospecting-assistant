"""Output module for the research pipeline.

Accepts the original prospect dict and the parsed Claude brand brief, merges
them into a structured final brief object, and writes it as a pretty-printed
JSON file under the /briefs/ directory.

The output filename is derived from a slugified version of the business name.
Example: "Glow Aesthetics & Med Spa NYC" → briefs/glow-aesthetics-med-spa-nyc.json

Dependencies:
  - pipeline.utils.slugify
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.utils import setup_logger, slugify

logger = setup_logger("pipeline.output")

# The model name is embedded in pipeline_meta for traceability.
MODEL = "claude-sonnet-4-20250514"

# Briefs are written relative to the current working directory (the script root).
BRIEFS_DIR = Path("briefs")

# Strip emoji characters before brief JSON can be reused as website content.
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # regional indicators
    "\U0001F300-\U0001F5FF"  # symbols and pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport and map
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"          # miscellaneous symbols
    "\u2700-\u27BF"          # dingbats
    "\uFE0F"                 # emoji variation selector
    "]+",
    flags=re.UNICODE,
)


def sanitize_website_content(value: Any) -> Any:
    """Recursively remove emoji characters from generated website content."""
    if isinstance(value, str):
        return EMOJI_RE.sub("", value).strip()
    if isinstance(value, list):
        return [sanitize_website_content(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_website_content(item) for key, item in value.items()}
    return value


def build_brief(
    prospect: dict[str, Any],
    brand_brief: dict[str, Any],
) -> dict[str, Any]:
    """Merge prospect data and Claude output into a single structured brief object.

    The returned dict has three top-level keys:
      - business_info: The original prospect dict from Google Sheets.
      - brand_brief:   The parsed JSON from the Claude research agent.
      - pipeline_meta: Provenance metadata (place_id, timestamp, model, status).

    Args:
        prospect: Original prospect dict keyed by SHEET_COLUMNS.
        brand_brief: Parsed JSON dict returned by run_research_agent().

    Returns:
        A fully merged brief dict ready for serialization.
    """
    return {
        "business_info": prospect,
        "brand_brief": sanitize_website_content(brand_brief),
        "pipeline_meta": {
            "place_id": prospect.get("Place ID", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": MODEL,
            "status": "complete",
        },
    }


def write_brief(
    prospect: dict[str, Any],
    brand_brief: dict[str, Any],
) -> str:
    """Build, serialize, and write the final brief to briefs/<slug>.json.

    Creates the briefs/ directory if it does not exist. Uses the business
    name to derive the output filename via slugify().

    Args:
        prospect: Original prospect dict keyed by SHEET_COLUMNS.
        brand_brief: Parsed JSON dict returned by run_research_agent().

    Returns:
        The output file path as a string (e.g. "briefs/glow-aesthetics-med-spa-nyc.json").
    """
    brief = build_brief(prospect, brand_brief)

    business_name = prospect.get("Business Name", "unknown-business")
    slug = slugify(business_name)

    # Ensure the briefs output directory exists before writing
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = BRIEFS_DIR / f"{slug}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)

    logger.info("Brief written to: %s", output_path)
    return str(output_path)
