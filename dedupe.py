"""Deduplication helpers for prospect records."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from utils import clean_phone, normalize_text, normalize_website


def build_dedupe_index(records: list[dict[str, Any]]) -> dict[str, set[str] | list[tuple[str, str]]]:
    return {
        "place_ids": {normalize_text(row.get("Place ID") or row.get("place_id")) for row in records if row.get("Place ID") or row.get("place_id")},
        "phones": {clean_phone(row.get("Phone") or row.get("phone")) for row in records if clean_phone(row.get("Phone") or row.get("phone"))},
        "websites": {normalize_website(row.get("Website") or row.get("website")) for row in records if normalize_website(row.get("Website") or row.get("website"))},
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
    place_id = normalize_text(prospect.get("place_id"))
    if place_id and place_id in index["place_ids"]:
        return True

    phone = clean_phone(prospect.get("phone"))
    if phone and phone in index["phones"]:
        return True

    website = normalize_website(prospect.get("website"))
    if website and website in index["websites"]:
        return True

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
