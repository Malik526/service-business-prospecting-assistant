"""Tests for dynamic PROSPECTS schema mapping.

These tests cover local, API-free behavior for column mapping, row
serialization, and email backfill queue construction.
"""

from __future__ import annotations

import unittest

from backfill_emails import build_enrichment_queue
from google_sheets import (
    GoogleSheetsClient,
    SHEET_COLUMNS,
    build_schema,
    column_index_to_letter,
    prospect_to_sheet_row,
)


class DynamicSchemaTests(unittest.TestCase):
    """Validate dynamic schema behavior without Google Sheets API calls."""

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
        """Find Website and Email values even when columns are rearranged."""
        schema = build_schema(["Email", "Business Name", "Website"])
        rows = [
            ["", "Ready Plumbing", "https://ready.example"],
            ["team@example.com", "Done HVAC", "https://done.example"],
            ["", "No Site Electric", ""],
        ]

        queue = build_enrichment_queue(
            rows,
            schema,
            schema.columns["Website"],
            schema.columns["Email"],
        )

        self.assertEqual(
            queue,
            [
                {
                    "row_index": 2,
                    "business_name": "Ready Plumbing",
                    "website": "https://ready.example",
                }
            ],
        )

    def test_default_schema_cache_shape_matches_columns(self) -> None:
        """Confirm the default canonical schema still has unique headers."""
        schema = build_schema(SHEET_COLUMNS)
        self.assertEqual(len(schema.headers), len(schema.columns))
        self.assertEqual(schema.columns["Place ID"], 0)
        self.assertEqual(schema.columns["Email"], 20)

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
