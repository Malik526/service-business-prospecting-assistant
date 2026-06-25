"""Tests for dynamic PROSPECTS schema mapping.

These tests cover local, API-free behavior for column mapping, row
serialization, and email backfill queue construction.
"""

from __future__ import annotations

import unittest

from backfill_emails import apply_checkpoint_filter, build_enrichment_queue
from categories import filter_target_categories
from google_sheets import (
    ADDRESS_COMPONENT_COLUMNS,
    GoogleSheetsClient,
    SHEET_COLUMNS,
    build_schema,
    column_index_to_letter,
    prospect_to_sheet_row,
)
from pipeline.address import parse_address


class DynamicSchemaTests(unittest.TestCase):
    """Validate dynamic schema behavior without Google Sheets API calls."""

    def test_filter_target_categories_accepts_singular_cli_names(self) -> None:
        """Resolve comma-separated category shorthands into target categories."""
        categories = filter_target_categories("electrician,hvac,plumber")

        self.assertEqual(
            [category["name"] for category in categories],
            ["electricians", "HVAC", "plumbers"],
        )

    def test_filter_target_categories_defaults_to_all_categories(self) -> None:
        """Return the full category list when no CLI filter is supplied."""
        self.assertGreater(len(filter_target_categories(None)), 3)

    def test_filter_target_categories_rejects_unknown_names(self) -> None:
        """Raise a clear error instead of silently ignoring unknown filters."""
        with self.assertRaisesRegex(ValueError, "Unknown categories: astrologer"):
            filter_target_categories("plumber,astrologer")

    def test_column_index_to_letter_supports_beyond_z(self) -> None:
        """Convert zero-based indexes into Sheets letters past column Z."""
        self.assertEqual(column_index_to_letter(0), "A")
        self.assertEqual(column_index_to_letter(25), "Z")
        self.assertEqual(column_index_to_letter(26), "AA")
        self.assertEqual(column_index_to_letter(27), "AB")

    def test_prospect_row_follows_rearranged_headers(self) -> None:
        """Place prospect values in the columns named by the live schema."""
        headers = [
            "Email",
            "Status",
            "Place ID",
            "Phone",
            "Last Outcome",
            "Business Name",
        ]
        schema = build_schema(headers)
        row = prospect_to_sheet_row(
            {
                "place_id": "abc123",
                "business_name": "Ridge Electric",
                "phone": "555-111-2222",
                "email": "hello@example.com",
            },
            schema,
        )

        self.assertEqual(row[0], "hello@example.com")
        self.assertEqual(row[1], "New")
        self.assertEqual(row[2], "abc123")
        self.assertEqual(row[3], "555-111-2222")
        self.assertEqual(row[4], "")
        self.assertEqual(row[5], "Ridge Electric")

    def test_prospect_row_skips_deleted_columns(self) -> None:
        """Serialize without raising when optional headers have been deleted."""
        schema = build_schema(["Business Name", "Email"])
        row = prospect_to_sheet_row(
            {
                "place_id": "missing-place-id-column",
                "business_name": "Maple HVAC",
                "email": "office@example.com",
                "status": "New",
            },
            schema,
        )

        self.assertEqual(row, ["Maple HVAC", "office@example.com"])

    def test_build_enrichment_queue_uses_schema_mapping(self) -> None:
        """Find Website, Email, and Instagram values when columns are rearranged."""
        schema = build_schema(["Email", "Business Name", "Instagram URL", "Website"])
        rows = [
            ["", "Ready Plumbing", "", "https://ready.example"],
            ["team@example.com", "Needs Social HVAC", "", "https://social.example"],
            ["", "Needs Email Electric", "https://instagram.com/electric", "https://electric.example"],
            ["team@example.com", "Done HVAC", "https://instagram.com/done", "https://done.example"],
            ["", "No Site Electric", "", ""],
        ]

        queue = build_enrichment_queue(
            rows,
            schema,
            schema.columns["Website"],
            {
                "email": schema.columns["Email"],
                "instagram_url": schema.columns["Instagram URL"],
            },
            ["email", "instagram_url"],
        )

        self.assertEqual(
            queue,
            [
                {
                    "row_index": 2,
                    "business_name": "Ready Plumbing",
                    "website": "https://ready.example",
                    "targets": ["email", "instagram_url"],
                },
                {
                    "row_index": 3,
                    "business_name": "Needs Social HVAC",
                    "website": "https://social.example",
                    "targets": ["instagram_url"],
                },
                {
                    "row_index": 4,
                    "business_name": "Needs Email Electric",
                    "website": "https://electric.example",
                    "targets": ["email"],
                }
            ],
        )

    def test_build_enrichment_queue_respects_skip_email_target(self) -> None:
        """Queue only Instagram rows when email extraction is skipped."""
        schema = build_schema(["Email", "Instagram URL", "Website"])
        rows = [
            ["", "", "https://both.example"],
            ["", "https://instagram.com/done", "https://email-only.example"],
        ]

        queue = build_enrichment_queue(
            rows,
            schema,
            schema.columns["Website"],
            {"instagram_url": schema.columns["Instagram URL"]},
            ["instagram_url"],
        )

        self.assertEqual(
            queue,
            [
                {
                    "row_index": 2,
                    "business_name": "",
                    "website": "https://both.example",
                    "targets": ["instagram_url"],
                }
            ],
        )

    def test_apply_checkpoint_filter_is_target_specific(self) -> None:
        """Resume should skip attempted fields without hiding other missing fields."""
        queue = [
            {
                "row_index": 2,
                "business_name": "Ready Plumbing",
                "website": "https://ready.example",
                "targets": ["email", "instagram_url"],
            },
            {
                "row_index": 3,
                "business_name": "Done HVAC",
                "website": "https://done.example",
                "targets": ["email"],
            },
        ]

        filtered = apply_checkpoint_filter(
            queue,
            {"email": {2, 3}, "instagram_url": set()},
        )

        self.assertEqual(
            filtered,
            [
                {
                    "row_index": 2,
                    "business_name": "Ready Plumbing",
                    "website": "https://ready.example",
                    "targets": ["instagram_url"],
                }
            ],
        )

    def test_default_schema_cache_shape_matches_columns(self) -> None:
        """Confirm the default canonical schema still has unique headers."""
        schema = build_schema(SHEET_COLUMNS)
        self.assertEqual(len(schema.headers), len(schema.columns))
        self.assertEqual(schema.columns["Place ID"], 0)
        self.assertEqual(schema.columns["Email"], 20)
        self.assertEqual(schema.columns["Street"], 21)
        self.assertEqual(schema.columns["City"], 22)
        self.assertEqual(schema.columns["State"], 23)
        self.assertEqual(schema.columns["ZIP"], 24)

    def test_prospect_row_includes_parsed_address_fields(self) -> None:
        """Serialize parsed address components into the default schema."""
        schema = build_schema(SHEET_COLUMNS)
        row = prospect_to_sheet_row(
            {
                "business_name": "Ridge Electric",
                "street": "6079 Myrtle Ave",
                "city": "Ridgewood",
                "state": "NY",
                "zip": "11385",
            },
            schema,
        )

        self.assertEqual(row[schema.columns["Street"]], "6079 Myrtle Ave")
        self.assertEqual(row[schema.columns["City"]], "Ridgewood")
        self.assertEqual(row[schema.columns["State"]], "NY")
        self.assertEqual(row[schema.columns["ZIP"]], "11385")

    def test_parse_address_extracts_google_places_components(self) -> None:
        """Parse the standard Google Places address format into components."""
        self.assertEqual(
            parse_address("6079 Myrtle Ave, Ridgewood, NY 11385, USA"),
            {
                "street": "6079 Myrtle Ave",
                "city": "Ridgewood",
                "state": "NY",
                "zip": "11385",
            },
        )

    def test_parse_address_returns_empty_parts_on_failure(self) -> None:
        """Return empty address parts instead of raising on invalid input."""
        with self.assertLogs("pipeline.address", level="WARNING") as captured_logs:
            result = parse_address("Ridgewood, NY")

        self.assertEqual(result, {"street": "", "city": "", "state": "", "zip": ""})
        self.assertIn("Could not parse address 'Ridgewood, NY'", captured_logs.output[0])

    def test_address_headers_are_appended_to_existing_sheets(self) -> None:
        """Append parsed address headers without changing existing header order."""
        client = object.__new__(GoogleSheetsClient)
        client.sheet_name = "PROSPECTS"
        update_calls = []

        class FakeValues:
            """Minimal fake Sheets values service for header update assertions."""

            def update(self, **kwargs: object) -> "FakeValues":
                """Record the update call and return an executable object."""
                update_calls.append(kwargs)
                return self

            def execute(self) -> dict[str, object]:
                """Return a fake successful Sheets API response."""
                return {}

        class FakeSpreadsheets:
            """Minimal fake Sheets spreadsheets service for tests."""

            def values(self) -> FakeValues:
                """Return fake values operations."""
                return FakeValues()

        class FakeService:
            """Minimal fake Sheets service for tests."""

            def spreadsheets(self) -> FakeSpreadsheets:
                """Return fake spreadsheet operations."""
                return FakeSpreadsheets()

        client.sheet_id = "sheet-123"
        client.service = FakeService()
        headers = ["Place ID", "Business Name", "Email"]

        updated_headers = client._ensure_address_component_headers(headers)

        self.assertEqual(updated_headers, headers + ADDRESS_COMPONENT_COLUMNS)
        self.assertEqual(update_calls[0]["range"], "PROSPECTS!D1:G1")
        self.assertEqual(update_calls[0]["body"], {"values": [ADDRESS_COMPONENT_COLUMNS]})

    def test_existing_place_ids_use_mapped_column(self) -> None:
        """Read Place IDs from the live mapped column rather than column A."""
        schema = build_schema(["Business Name", "Phone", "Place ID"])
        client = object.__new__(GoogleSheetsClient)
        client.sheet_name = "PROSPECTS"
        requested_ranges = []

        def fake_get_values(sheet_range: str) -> list[list[str]]:
            """Capture the requested range and return fake Place IDs."""
            requested_ranges.append(sheet_range)
            return [["place-one"], [""], ["place-two"]]

        client._get_values = fake_get_values

        self.assertEqual(
            client.get_existing_place_ids(schema),
            {"place-one", "place-two"},
        )
        self.assertEqual(requested_ranges, ["PROSPECTS!C2:C"])

    def test_dropdown_validation_uses_mapped_column(self) -> None:
        """Build dropdown validation for the live Status column index."""
        schema = build_schema(["Business Name", "Status"])
        client = object.__new__(GoogleSheetsClient)
        request = client._validation_request(
            sheet_gid=123,
            column_name="Status",
            options=["New"],
            schema=schema,
        )

        validation_range = request["setDataValidation"]["range"]
        self.assertEqual(validation_range["startColumnIndex"], 1)
        self.assertEqual(validation_range["endColumnIndex"], 2)


if __name__ == "__main__":
    unittest.main()
