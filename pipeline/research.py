"""Business research agent using the Claude API.

Accepts a prospect dict (as returned by GoogleSheetsClient.get_record_by_place_id,
keyed by SHEET_COLUMNS) and calls claude-sonnet-4-5 to produce a structured
brand brief JSON object.

Dependencies:
  - anthropic Python SDK
  - pipeline.utils.setup_logger

Note:
  The prospect dict keys are the raw Google Sheet column names (e.g. "Business Name",
  "Place ID") because they come directly from get_existing_records() via get_record_by_place_id().
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from pipeline.utils import setup_logger

logger = setup_logger("pipeline.research")

# The Claude model to use for all research calls.
MODEL = "claude-sonnet-4-5"

# System prompt defining the agent's role and output expectations.
SYSTEM_PROMPT = (
    "You are a business research agent for a growth agency that builds "
    "websites and growth systems for local service businesses. Given a "
    "prospect's data from Google Maps, produce a structured brand brief "
    "that will be used to build their website, write their cold call "
    "script, and optimize their SEO. Be specific, practical, and "
    "grounded in the data provided."
)

# The exact keys expected in Claude's JSON response.
EXPECTED_BRIEF_KEYS = [
    "brand_voice",
    "visual_direction",
    "headline_suggestion",
    "subheadline_suggestion",
    "key_services",
    "review_themes",
    "cold_call_hook",
    "seo_keywords",
    "website_sections",
    "owner_note",
]


def build_user_prompt(
    prospect: dict[str, Any],
    reviews: list[dict] | None = None
) -> str:
    """Construct the structured user prompt from a prospect dict.

    Formats all relevant prospect fields into a readable block and appends
    a strict JSON-only instruction so Claude returns only parseable output.

    Args:
        prospect: Prospect dict keyed by SHEET_COLUMNS values.
        reviews: Optional list of five-star review dicts from Google Places API.
                 When provided, real customer review text is appended to the
                 prompt so Claude grounds the brief in actual feedback rather
                 than category-level assumptions.

    Returns:
        The formatted user prompt string to send to Claude.
    """
    # Conditionally include website only if one exists
    website_line = (
        f"Website: {prospect['Website']}"
        if prospect.get("Website")
        else "Website: None"
    )

    # Append real review text if available so Claude uses actual
    # customer language rather than generic category assumptions.
    review_block = ""
    if reviews:
        review_block = "\n\nReal Five-Star Google Reviews (use these to inform\n"
        review_block += "brand voice, review themes, and cold call hook):\n"
        for i, review in enumerate(reviews, 1):
            review_block += (
                f"\n{i}. {review.get('author_name', 'Anonymous')} "
                f"({review.get('rating', 5)} stars, "
                f"{review.get('relative_time_description', 'recently')}):\n"
                f"\"{review.get('text', '').strip()}\"\n"
            )

    return f"""Here is the prospect data from Google Maps:

Business Name: {prospect.get("Business Name", "N/A")}
Category: {prospect.get("Category", "N/A")}
Address: {prospect.get("Address", "N/A")}
Phone: {prospect.get("Phone", "N/A")}
{website_line}
Rating: {prospect.get("Rating", "N/A")}
Review Count: {prospect.get("Review Count", "N/A")}
Weighted Reputation Score: {prospect.get("Weighted Reputation Score", "N/A")}
Why Good Fit: {prospect.get("Why Good Fit", "N/A")}
Lead Score: {prospect.get("Lead Score", "N/A")}
{review_block}
Return ONLY a valid JSON object with exactly these keys:
{{
  "brand_voice": "string — tone, personality, and voice this brand should use",
  "visual_direction": "string — colors, style, and visual identity direction",
  "headline_suggestion": "string — a compelling homepage headline",
  "subheadline_suggestion": "string — a supporting subheadline",
  "key_services": ["list of their core service offerings"],
  "review_themes": ["list of sentiment themes likely found in their reviews"],
  "cold_call_hook": "string — opening line for a cold call to this business",
  "seo_keywords": ["list of relevant local SEO keyword phrases"],
  "website_sections": ["list of recommended website page sections"],
  "owner_note": "string — personal note about what makes this business worth working with"
}}

Do not include any explanation, markdown, or extra text. Return only the JSON object."""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fence wrappers if Claude wraps the JSON in them.

    Handles both ```json ... ``` and plain ``` ... ``` wrapping.
    Returns the text unchanged if no fences are detected.
    """
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    # Drop the opening fence line (e.g. ```json or ```)
    start = 1
    # Drop the closing fence line if present
    end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
    return "\n".join(lines[start:end])


def run_research_agent(
    prospect: dict[str, Any],
    api_key: str,
    reviews: list[dict] | None = None,
) -> dict[str, Any] | None:
    """Call Claude and return the parsed brand brief dict.

    Sends the formatted prospect prompt to claude-sonnet-4-5. Parses
    the response as JSON and returns it. If Claude returns malformed output
    (e.g. wrapped in markdown, truncated, or invalid JSON), logs the error
    and returns None so the caller can handle the failure gracefully.

    Args:
        prospect: Prospect dict keyed by SHEET_COLUMNS values.
        api_key: Anthropic API key string.
        reviews: Optional list of five-star review dicts. When provided,
                 real customer language is included in the prompt so Claude
                 does not hallucinate review themes or brand voice.

    Returns:
        Parsed brand brief dict with EXPECTED_BRIEF_KEYS, or None on failure.
    """
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = build_user_prompt(prospect, reviews=reviews)

    logger.info(
        "Sending research request to %s for: %s",
        MODEL,
        prospect.get("Business Name", "unknown"),
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = message.content[0].text.strip()
    cleaned = _strip_code_fences(raw_text)

    try:
        result = json.loads(cleaned)
        logger.info("Research agent returned valid JSON for: %s", prospect.get("Business Name"))
        return result
    except (json.JSONDecodeError, IndexError, KeyError) as exc:
        logger.error("Failed to parse Claude response as JSON: %s", exc)
        logger.error("Raw response was:\n%s", raw_text)
        return None
