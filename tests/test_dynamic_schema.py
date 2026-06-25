"""Tests for dynamic PROSPECTS schema mapping.

These tests cover local, API-free behavior for column mapping, row
serialization, and email backfill queue construction.
"""

from __future__ import annotations

import subprocess
import sys
import time
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import mock_open, patch

from backfill_emails import apply_checkpoint_filter, build_enrichment_queue
from categories import filter_target_categories
from google_places import GooglePlacesClient
from google_sheets import (
    ADDRESS_COMPONENT_COLUMNS,
    DATE_ADDED_COLUMN,
    DATE_ADDED_COLUMN_INDEX,
    GoogleSheetsClient,
    SHEET_COLUMNS,
    acquire_sheet_lock,
    build_schema,
    column_index_to_letter,
    prospect_to_sheet_row,
    release_sheet_lock,
)
from main import extract_address_components, selected_extractors


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

    def test_selected_extractors_defaults_to_email_and_instagram(self) -> None:
        """Enable both main-pipeline extractors unless they are skipped."""
        args = Namespace(skip_email=False, skip_instagram=False)

        self.assertEqual(selected_extractors(args), ["email", "instagram_url"])

    def test_selected_extractors_supports_google_data_only(self) -> None:
        """Disable all contact extraction when both skip flags are present."""
        args = Namespace(skip_email=True, skip_instagram=True)

        self.assertEqual(selected_extractors(args), [])

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
        self.assertEqual(schema.columns["Date Added"], 1)
        self.assertEqual(schema.columns["Email"], 21)
        self.assertEqual(schema.columns["Street"], 22)
        self.assertEqual(schema.columns["City"], 23)
        self.assertEqual(schema.columns["State"], 24)
        self.assertEqual(schema.columns["ZIP"], 25)

    def test_prospect_row_includes_date_added(self) -> None:
        """Serialize Date Added into column B of the default schema."""
        schema = build_schema(SHEET_COLUMNS)
        row = prospect_to_sheet_row(
            {
                "place_id": "abc123",
                "date_added": "2026-06-25",
                "business_name": "Ridge Electric",
            },
            schema,
        )

        self.assertEqual(row[0], "abc123")
        self.assertEqual(row[1], "2026-06-25")
        self.assertEqual(row[2], "Ridge Electric")

    def test_prospect_row_includes_parsed_address_fields(self) -> None:
        """Serialize API address components into the default schema."""
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

    def test_extract_address_components_uses_google_places_components(self) -> None:
        """Extract sheet address fields from Google Places component types."""
        self.assertEqual(
            extract_address_components(
                [
                    {
                        "long_name": "6079",
                        "short_name": "6079",
                        "types": ["street_number"],
                    },
                    {
                        "long_name": "Myrtle Ave",
                        "short_name": "Myrtle Ave",
                        "types": ["route"],
                    },
                    {
                        "long_name": "Ridgewood",
                        "short_name": "Ridgewood",
                        "types": ["locality"],
                    },
                    {
                        "long_name": "New York",
                        "short_name": "NY",
                        "types": ["administrative_area_level_1", "political"],
                    },
                    {
                        "long_name": "11385",
                        "short_name": "11385",
                        "types": ["postal_code"],
                    },
                ]
            ),
            {
                "street": "6079 Myrtle Ave",
                "city": "Ridgewood",
                "state": "NY",
                "zip": "11385",
            },
        )

    def test_extract_address_components_returns_empty_parts_when_missing(self) -> None:
        """Return empty address parts when Google omits component data."""
        result = extract_address_components([])

        self.assertEqual(result, {"street": "", "city": "", "state": "", "zip": ""})

    def test_place_details_requests_address_components(self) -> None:
        """Request Google Places address_components in Place Details fields."""
        captured_params = {}

        class FakeResponse:
            """Minimal response object for Place Details request assertions."""

            def raise_for_status(self) -> None:
                """Simulate a successful HTTP response."""
                return None

            def json(self) -> dict[str, object]:
                """Return a minimal OK Place Details payload."""
                return {"status": "OK", "result": {"address_components": []}}

        def fake_get(url: str, params: dict[str, str], timeout: int) -> FakeResponse:
            """Capture request params and return a fake Places response."""
            captured_params.update(params)
            return FakeResponse()

        client = GooglePlacesClient(api_key="test-key")
        with patch("google_places.requests.get", side_effect=fake_get):
            client.get_place_details("place-123")

        self.assertIn("address_components", captured_params["fields"])

    def test_address_headers_are_appended_to_existing_sheets(self) -> None:
        """Append address component headers without changing existing header order."""
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

    def test_date_added_header_is_inserted_at_column_b(self) -> None:
        """Insert Date Added at column B without replacing existing headers."""
        client = object.__new__(GoogleSheetsClient)
        client.sheet_name = "PROSPECTS"
        client.sheet_id = "sheet-123"
        batch_calls = []
        value_updates = []

        class FakeValues:
            """Minimal fake values service for Date Added header assertions."""

            def update(self, **kwargs: object) -> "FakeValues":
                """Record value update calls and return an executable object."""
                value_updates.append(kwargs)
                return self

            def execute(self) -> dict[str, object]:
                """Return a fake successful values API response."""
                return {}

        class FakeSpreadsheets:
            """Minimal fake spreadsheets service for column insertion assertions."""

            def batchUpdate(self, **kwargs: object) -> "FakeSpreadsheets":
                """Record batch update calls and return an executable object."""
                batch_calls.append(kwargs)
                return self

            def values(self) -> FakeValues:
                """Return fake values operations."""
                return FakeValues()

            def execute(self) -> dict[str, object]:
                """Return fake spreadsheet metadata or update response."""
                return {}

        class FakeService:
            """Minimal fake Sheets service for tests."""

            def spreadsheets(self) -> FakeSpreadsheets:
                """Return fake spreadsheet operations."""
                return FakeSpreadsheets()

        client.service = FakeService()
        client._get_sheet_gid = lambda: 123
        headers = ["Place ID", "Business Name", "Category"]

        updated_headers = client._ensure_date_added_header(headers)

        self.assertEqual(
            updated_headers,
            ["Place ID", DATE_ADDED_COLUMN, "Business Name", "Category"],
        )
        insert_range = batch_calls[0]["body"]["requests"][0]["insertDimension"]["range"]
        self.assertEqual(insert_range["startIndex"], DATE_ADDED_COLUMN_INDEX)
        self.assertEqual(insert_range["endIndex"], DATE_ADDED_COLUMN_INDEX + 1)
        self.assertEqual(value_updates[0]["range"], "PROSPECTS!B1")
        self.assertEqual(value_updates[0]["body"], {"values": [[DATE_ADDED_COLUMN]]})

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

    def test_append_prospects_wraps_write_with_lock(self) -> None:
        """Acquire and release the sheet lock around the append critical section."""
        schema = build_schema(["Place ID", "Business Name", "Status"])
        client = object.__new__(GoogleSheetsClient)
        client.sheet_id = "sheet-123"
        client.sheet_name = "PROSPECTS"
        client.ensure_header = lambda: schema
        client.get_existing_place_ids = lambda _schema: set()
        validation_calls = []
        client.apply_dropdown_validations = lambda schema=None: validation_calls.append(schema)
        append_calls = []

        class FakeValues:
            def append(self, **kwargs: object) -> "FakeValues":
                append_calls.append(kwargs)
                return self

            def execute(self) -> dict[str, object]:
                return {}

        class FakeSpreadsheets:
            def values(self) -> FakeValues:
                return FakeValues()

        class FakeService:
            def spreadsheets(self) -> FakeSpreadsheets:
                return FakeSpreadsheets()

        client.service = FakeService()

        with patch("google_sheets.acquire_sheet_lock", return_value="lock-handle") as acquire_mock, patch(
            "google_sheets.release_sheet_lock"
        ) as release_mock:
            result = client.append_prospects(
                [{"place_id": "place-1", "business_name": "Ridge Electric"}]
            )

        self.assertEqual(result, {"appended": 1, "skipped_duplicates": 0})
        acquire_mock.assert_called_once_with(timeout=30)
        release_mock.assert_called_once_with("lock-handle")
        self.assertEqual(append_calls[0]["spreadsheetId"], "sheet-123")
        self.assertEqual(append_calls[0]["range"], "PROSPECTS!A:C")
        self.assertEqual(validation_calls, [schema])

    def test_acquire_sheet_lock_times_out(self) -> None:
        """Raise TimeoutError when the file lock cannot be acquired in time."""
        with patch("google_sheets.open", mock_open(), create=True), patch(
            "google_sheets.fcntl.flock",
            side_effect=OSError("busy"),
        ), patch("google_sheets.time.time", side_effect=[0.0, 31.0]), patch(
            "google_sheets.time.sleep"
        ):
            with self.assertRaisesRegex(TimeoutError, "Could not acquire sheet lock"):
                acquire_sheet_lock(timeout=30)

    def test_sheet_lock_blocks_parallel_processes(self) -> None:
        """A second process should wait until the first releases the lock."""
        repo_root = Path(__file__).resolve().parents[1]
        script = (
            "from google_sheets import acquire_sheet_lock, release_sheet_lock\n"
            "lock = acquire_sheet_lock(timeout=2)\n"
            "print('child-acquired', flush=True)\n"
            "release_sheet_lock(lock)\n"
        )

        lock_file = acquire_sheet_lock(timeout=2)
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", script],
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.6)
            self.assertIsNone(process.poll())
        finally:
            release_sheet_lock(lock_file)

        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, msg=stderr)
        self.assertIn("child-acquired", stdout)


if __name__ == "__main__":
    unittest.main()
