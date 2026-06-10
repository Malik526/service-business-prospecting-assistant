"""Google Sheets storage client.

This module handles all interaction with the Google Sheets API:
  - Ensuring the header row exists with the correct columns.
  - Migrating older prospect headers into the current PROSPECTS schema.
  - Applying dropdown validation to controlled outreach columns.
  - Reading existing records for deduplication.
  - Appending new prospect rows.

Authentication uses a service account (not OAuth user login). The Google Sheet
must be shared with the service account email as an Editor — without this,
reads and writes will fail with a 403 permission error even if authentication
itself succeeds.

Column Layout (A–U)
-------------------
A  Place ID
B  Business Name
C  Category
D  Address
E  Phone
F  Website
G  Google Maps URL
H  Rating
I  Review Count
J  Distance From Search ZIP (mi)
K  Source
L  Lead Score
M  Why Good Fit
N  Status
O  Last Contact Date        ← Manual outreach tracking
P  Last Outcome             ← Manual outreach tracking
Q  Notes
R  Search ZIP Code          ← ZIP code used in the discovery run (auto-populated)
S  Search Radius (mi)       ← Radius used in the discovery run (auto-populated)
T  Instagram URL            ← Extracted from business website (auto-populated)
U  Email                    ← Extracted from business website (auto-populated)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Ordered list of column headers. The order here defines the column layout in
# the Google Sheet and must match `prospect_to_sheet_row` exactly.
SHEET_COLUMNS = [
    "Place ID",
    "Business Name",
    "Category",
    "Address",
    "Phone",
    "Website",
    "Google Maps URL",
    "Rating",
    "Review Count",
    "Distance From Search ZIP (mi)",
    "Source",
    "Lead Score",
    "Why Good Fit",
    "Status",
    "Last Contact Date",
    "Last Outcome",
    "Notes",
    "Search ZIP Code",        # Column R — ZIP used in the discovery run
    "Search Radius (mi)",     # Column S — radius used in the discovery run
    "Instagram URL",          # Column T — extracted from business website (auto-populated)
    "Email",                  # Column U — extracted from business website (auto-populated)
]

# Column letter of the last column, derived from SHEET_COLUMNS length.
# Update this if columns are added or removed.
_LAST_COL = "U"  # 21 columns: A through U

# Older releases wrote extra CRM/date/reputation columns through W. Read and
# clear that full width during one-time schema normalization so old trailing
# cells do not remain visible after the PROSPECTS header is written.
_LEGACY_LAST_COL = "W"

# Allowed values for the Status dropdown. Status now represents prospect
# qualification only; call outcomes live in the Last Outcome column.
STATUS_OPTIONS = [
    "New",
    "Reviewed",
    "Good Fit",
    "Not Fit",
    "Do Not Contact",
    "Not Interested",
]

# Allowed values for the Last Outcome dropdown. Validation is non-strict so
# manual notes or future outcome names can be entered without breaking edits.
LAST_OUTCOME_OPTIONS = [
    "Not Called Yet",
    "Answered - Interested",
    "Answered - Not Interested",
    "Answered - Hung Up",
    "Answered - Scheduled Demo",
    "Voicemail Left",
    "Wrong Number",
    "Business Closed",
    "Do Not Call List",
]


class GoogleSheetsClient:
    def __init__(self, sheet_id: str, service_account_file: str, sheet_name: str) -> None:
        """Initialize the Sheets client using a service account credential file.

        Args:
            sheet_id: The Google Spreadsheet ID (from the URL).
            service_account_file: Local path to the service account JSON key file.
            sheet_name: The name of the tab/sheet within the spreadsheet.
        """
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(
            str(Path(service_account_file).expanduser()),
            scopes=scopes,
        )
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.service = build("sheets", "v4", credentials=credentials)

    def ensure_header(self) -> None:
        """Write the header row if it is missing or incorrect, then apply validation.

        Reads the first row of the sheet and compares it against SHEET_COLUMNS.
        If an older header is detected, existing rows are reshaped into the
        current PROSPECTS schema so manual Status and Notes values stay in
        their intended columns. Dropdown validation is applied on every call.
        """
        values = self._get_values(f"{self.sheet_name}!A1:{_LEGACY_LAST_COL}1")
        current_header = values[0] if values else []

        if current_header != SHEET_COLUMNS:
            if current_header:
                self._migrate_existing_rows(current_header)
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"{self.sheet_name}!A1:{_LAST_COL}1",
                valueInputOption="RAW",
                body={"values": [SHEET_COLUMNS]},
            ).execute()
            self._clear_values(f"{self.sheet_name}!V:W")

        # Apply dropdown validation every run (idempotent).
        self.apply_dropdown_validations()

    def get_existing_records(self) -> list[dict[str, Any]]:
        """Read all existing data rows from the sheet and return as a list of dicts.

        Called at the start of each run to build the deduplication index.
        Each row is padded to the full column width so that dicts always have
        all expected keys, even if a row in the sheet is missing trailing cells.

        Returns:
            List of dicts keyed by SHEET_COLUMNS values.
        """
        self.ensure_header()
        values = self._get_values(f"{self.sheet_name}!A2:{_LAST_COL}")
        records = []
        for row in values:
            # Pad short rows so every dict has the full set of column keys.
            padded = row + [""] * (len(SHEET_COLUMNS) - len(row))
            records.append(dict(zip(SHEET_COLUMNS, padded)))
        return records

    def get_record_by_place_id(self, place_id: str) -> dict | None:
        """Find and return a single row from the sheet matching the given Place ID.

        Reads all existing records and searches for a match in the
        'Place ID' column. Returns the row as a dict keyed by SHEET_COLUMNS,
        or None if no match is found.

        Args:
            place_id: The Google Maps Place ID to search for.
        """
        records = self.get_existing_records()
        for record in records:
            if record.get("Place ID") == place_id:
                return record
        return None

    def append_prospects(self, prospects: list[dict[str, Any]]) -> dict[str, int]:
        """Append new prospect rows to the bottom of the sheet.

        Uses INSERT_ROWS mode so existing data is never overwritten.
        Existing Place IDs are queried immediately before append so duplicate
        rows are skipped even if a caller did not run the upstream dedupe pass.

        Args:
            prospects: List of enriched prospect dicts (post-deduplication and scoring).

        Returns:
            Counts for appended rows and duplicate Place IDs skipped.
        """
        if not prospects:
            return {"appended": 0, "skipped_duplicates": 0}

        existing_place_ids = {
            str(record.get("Place ID", "")).strip()
            for record in self.get_existing_records()
            if str(record.get("Place ID", "")).strip()
        }

        appendable = []
        skipped_duplicates = 0
        for prospect in prospects:
            place_id = str(prospect.get("place_id", "")).strip()
            if place_id and place_id in existing_place_ids:
                skipped_duplicates += 1
                continue
            appendable.append(prospect)
            if place_id:
                existing_place_ids.add(place_id)

        if not appendable:
            logger.info(
                "No new prospects appended. Skipped %d duplicate Place ID(s).",
                skipped_duplicates,
            )
            return {"appended": 0, "skipped_duplicates": skipped_duplicates}

        rows = [prospect_to_sheet_row(prospect) for prospect in appendable]
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A:{_LAST_COL}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

        self.apply_dropdown_validations()
        logger.info(
            "Appended %d prospect(s). Skipped %d duplicate Place ID(s).",
            len(appendable),
            skipped_duplicates,
        )
        return {"appended": len(appendable), "skipped_duplicates": skipped_duplicates}

    def apply_dropdown_validations(self) -> None:
        """Apply dropdown validation rules to controlled PROSPECTS columns.

        Uses the Sheets batchUpdate API with a `setDataValidation` request.
        Rules are applied to Status and Last Outcome for rows 2-10000.

        The validation covers rows 2–10000 (row 1 is the header). Applying
        this on every run is safe and idempotent — it does not reset existing
        cell values, only updates the validation rule.

        `strict=False` keeps the dropdown suggestions visible while allowing
        manual values that are not in the configured list.
        """
        sheet_gid = self._get_sheet_gid()
        requests = [
            self._validation_request(
                sheet_gid=sheet_gid,
                column_name="Status",
                options=STATUS_OPTIONS,
            ),
            self._validation_request(
                sheet_gid=sheet_gid,
                column_name="Last Outcome",
                options=LAST_OUTCOME_OPTIONS,
            ),
        ]

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": requests},
        ).execute()

    def _validation_request(
        self,
        sheet_gid: int,
        column_name: str,
        options: list[str],
    ) -> dict[str, Any]:
        """Build one Google Sheets data-validation request for a dropdown column."""
        column_index = SHEET_COLUMNS.index(column_name)
        return {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": 1,       # Row 2 (0-indexed) — skip the header
                    "endRowIndex": 10000,     # Cover all foreseeable future rows
                    "startColumnIndex": column_index,
                    "endColumnIndex": column_index + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": option} for option in options],
                    },
                    "showCustomUi": True,
                    "strict": False,
                },
            }
        }

    def _migrate_existing_rows(self, current_header: list[Any]) -> None:
        """Reshape old sheet rows into the current PROSPECTS column order."""
        normalized_header = [str(header).strip() for header in current_header]
        legacy_markers = [
            "Date Added",
            "Weighted Reputation Score",
            "Date Contacted",
            "Follow-Up Date",
        ]
        if not any(header in normalized_header for header in legacy_markers):
            return

        old_rows = self._get_values(f"{self.sheet_name}!A2:{_LEGACY_LAST_COL}")
        if not old_rows:
            return

        migrated_rows = []
        for row in old_rows:
            padded = row + [""] * (len(normalized_header) - len(row))
            record = dict(zip(normalized_header, padded))
            migrated_rows.append(
                [self._value_from_record(record, column) for column in SHEET_COLUMNS]
            )

        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A2:{_LAST_COL}",
            valueInputOption="RAW",
            body={"values": migrated_rows},
        ).execute()
        self._clear_values(f"{self.sheet_name}!V2:W")
        logger.info(
            "Migrated %d existing row(s) into the PROSPECTS schema.",
            len(migrated_rows),
        )

    def _value_from_record(self, record: dict[str, Any], column: str) -> Any:
        """Return the migrated value for a PROSPECTS column from an old row dict."""
        if column == "Last Contact Date":
            return record.get("Last Contact Date", "")
        if column == "Last Outcome":
            return record.get("Last Outcome", "")
        return record.get(column, "")

    def _get_sheet_gid(self) -> int:
        """Return the internal numeric sheet ID (gid) for self.sheet_name.

        The gid is an integer assigned by Google Sheets and is different from
        the spreadsheet ID in the URL. It is required by batchUpdate API calls
        such as setDataValidation. The gid for the first tab is typically 0,
        but this is not guaranteed — always look it up by tab name.

        Raises:
            ValueError: if no tab with self.sheet_name exists in the spreadsheet.
        """
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.sheet_id
        ).execute()
        for sheet in spreadsheet.get("sheets", []):
            if sheet["properties"]["title"] == self.sheet_name:
                return sheet["properties"]["sheetId"]
        raise ValueError(f"Sheet tab '{self.sheet_name}' not found in spreadsheet.")

    def _get_values(self, sheet_range: str) -> list[list[Any]]:
        """Read cell values from a named range and return as a 2D list.

        Returns an empty list if the range has no data, rather than raising.
        """
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=sheet_range,
        ).execute()
        return result.get("values", [])

    def _clear_values(self, sheet_range: str) -> None:
        """Clear values from a range without deleting rows or columns."""
        self.service.spreadsheets().values().clear(
            spreadsheetId=self.sheet_id,
            range=sheet_range,
            body={},
        ).execute()


def prospect_to_sheet_row(prospect: dict[str, Any]) -> list[Any]:
    """Serialize a prospect dict into an ordered list of cell values.

    The order must exactly match SHEET_COLUMNS. Missing keys default to
    empty string so partial prospects don't shift column alignment.
    """
    return [
        prospect.get("place_id", ""),
        prospect.get("business_name", ""),
        prospect.get("category", ""),
        prospect.get("address", ""),
        prospect.get("phone", ""),
        prospect.get("website", ""),
        prospect.get("google_maps_url", ""),
        prospect.get("rating", ""),
        prospect.get("review_count", ""),
        prospect.get("distance_miles", ""),
        prospect.get("source", ""),
        prospect.get("lead_score", ""),
        prospect.get("why_good_fit", ""),
        prospect.get("status") or "New",
        prospect.get("last_contact_date", ""),
        prospect.get("last_outcome", ""),
        prospect.get("notes", ""),
        prospect.get("search_zip", ""),
        prospect.get("search_radius", ""),
        prospect.get("instagram_url", ""),
        prospect.get("email", ""),
    ]
