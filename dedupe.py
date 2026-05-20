"""Deduplication helpers for prospect records.

Strategy
--------
A prospect is considered a duplicate if it matches an existing record on any
one of the following signals (checked in priority order):

  1. Place ID (exact match, normalized):
     Google's unique identifier for a business location. This is the most
     reliable dedupe key — if the Place ID matches, it is definitively the
     same business listing.

  2. Phone number (exact match after stripping formatting):
     Phones are stripped to digits only before comparison. Different formatting
     of the same number (e.g., "(212) 555-1234" vs "2125551234") should not
     create duplicates.

  3. Website (exact match after normalization):
     URLs are lowercased and stripped of protocol (http/https), www prefix,
     and trailing slashes. A business that appears under two slightly different
     URL formats should only be stored once.

  4. Business name + address similarity (fuzzy match):
     Used as a fallback when Place ID, phone, and website are all absent or
     differ. Checks both the name and address together using SequenceMatcher
     — a name-only match is insufficient because common names like "ABC Plumbing"
     may refer to different businesses in different cities. Both signals must
     exceed their respective thresholds simultaneously (name >= 0.9,
     address >= 0.85) to be flagged as a duplicate.

Fuzzy Thresholds
----------------
  - Name similarity >= 0.90:  Very close name match required (minor typos OK).
  - Address similarity >= 0.85: Slightly looser to handle address formatting
    differences (e.g., "St" vs "Street", suite number presence/absence).

In-run Deduplication
--------------------
The dedupe index is initialized from existing Google Sheet records at the
start of each run, then updated in-memory as new prospects are added within
the same run. This prevents two API results for the same business (which can
happen if a business appears in multiple category searches) from being written
as duplicate rows in the same batch.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from utils import clean_phone, normalize_text, normalize_website


def build_dedupe_index(records: list[dict[str, Any]]) -> dict[str, set[str] | list[tuple[str, str]]]:
    """Build a lookup index from existing sheet records for fast duplicate detection.

    The index is structured as a dict with four keys:
      - "place_ids":      Set of normalized Place ID strings.
      - "phones":         Set of digit-only phone strings.
      - "websites":       Set of normalized URL strings.
      - "name_addresses": List of (normalized_name, normalized_address) tuples
                          for fuzzy matching.

    Both PascalCase field names (from sheet rows) and snake_case names (from
    prospect dicts built during the current run) are handled — the sheet
    returns column-header-keyed dicts, while in-memory prospects use snake_case.

    Args:
        records: List of dicts from GoogleSheetsClient.get_existing_records().

    Returns:
        A dedupe index dict ready to pass to is_duplicate and add_to_index.
    """
    return {
        "place_ids": {
            normalize_text(row.get("Place ID") or row.get("place_id"))
            for row in records
            if row.get("Place ID") or row.get("place_id")
        },
        "phones": {
            clean_phone(row.get("Phone") or row.get("phone"))
            for row in records
            if clean_phone(row.get("Phone") or row.get("phone"))
        },
        "websites": {
            normalize_website(row.get("Website") or row.get("website"))
            for row in records
            if normalize_website(row.get("Website") or row.get("website"))
        },
        "name_addresses": [
            (
                normalize_text(row.get("Business Name") or row.get("business_name")),
                normalize_text(row.get("Address") or row.get("address")),
            )
            for row in records
            if row.get("Business Name") or row.get("business_name")
        ],
    }


def is_duplicate(prospect: dict[str, Any], index: dict[str, Any]) -> bool:
    """Return True if the prospect matches any record in the dedupe index.

    Checks each signal in priority order and short-circuits on the first match.
    See module docstring for full explanation of each check and its rationale.

    Args:
        prospect: A prospect dict from discover_prospects (snake_case keys).
        index: A dedupe index built by build_dedupe_index.

    Returns:
        True if the prospect is a duplicate of an existing record, else False.
    """
    # Check 1: Google Place ID — most authoritative signal.
    place_id = normalize_text(prospect.get("place_id"))
    if place_id and place_id in index["place_ids"]:
        return True

    # Check 2: Phone number (digits only).
    phone = clean_phone(prospect.get("phone"))
    if phone and phone in index["phones"]:
        return True

    # Check 3: Website URL (normalized).
    website = normalize_website(prospect.get("website"))
    if website and website in index["websites"]:
        return True

    # Check 4: Fuzzy name + address match (both must exceed threshold together).
    name = normalize_text(prospect.get("business_name"))
    address = normalize_text(prospect.get("address"))
    if name and address:
        for existing_name, existing_address in index["name_addresses"]:
            name_match = SequenceMatcher(None, name, existing_name).ratio()
            address_match = SequenceMatcher(None, address, existing_address).ratio()
            if name_match >= 0.9 and address_match >= 0.85:
                return True

    return False


def add_to_index(prospect: dict[str, Any], index: dict[str, Any]) -> None:
    """Add a prospect's signals to the dedupe index after it passes deduplication.

    Called immediately after a prospect is accepted as non-duplicate so that
    subsequent prospects in the same run are checked against it. This prevents
    within-run duplicates when the same business appears in multiple category
    search results.

    Args:
        prospect: An enriched prospect dict that has been accepted as new.
        index: The same dedupe index passed to is_duplicate — mutated in place.
    """
    place_id = normalize_text(prospect.get("place_id"))
    phone = clean_phone(prospect.get("phone"))
    website = normalize_website(prospect.get("website"))
    name = normalize_text(prospect.get("business_name"))
    address = normalize_text(prospect.get("address"))

    if place_id:
        index["place_ids"].add(place_id)
    if phone:
        index["phones"].add(phone)
    if website:
        index["websites"].add(website)
    if name or address:
        index["name_addresses"].append((name, address))
