"""Google Sheets storage client.

This module handles all interaction with the Google Sheets API:
  - Ensuring the header row exists with the correct columns.
  - Applying dropdown validation to the Status column so the sheet behaves
    like a lightweight CRM with constrained status transitions.
  - Reading existing records for deduplication.
  - Appending new prospect rows.

Authentication uses a service account (not OAuth user login). The Google Sheet
must be shared with the service account email as an Editor — without this,
reads and writes will fail with a 403 permission error even if authentication
itself succeeds.

Column Layout (A–Q)
-------------------
Place ID | Business Name | Category | Address | Phone | Website |
Google Maps URL | Rating | Review Count | Distance From Search ZIP (mi) |
Source | Lead Score | Why Good Fit | Status | Date Added | Notes |
Weighted Reputation Score
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


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
    "Date Added",
    "Notes",
    "Weighted Reputation Score",
]

# Column letter of the last column, derived from SHEET_COLUMNS length.
# Update this if columns are added or removed.
_LAST_COL = "Q"  # 17 columns: A through Q

# Allowed values for the Status dropdown. These represent the prospect's
# current stage in the outreach workflow, from initial discovery to close.
STATUS_OPTIONS = [
    "New",           # Just discovered, not yet reviewed
    "Reviewed",      # Manually reviewed, decision pending
    "Good Fit",      # Determined to be a strong outreach candidate
    "Not Fit",       # Reviewed and ruled out
    "Contacted",     # First outreach sent
    "Followed Up",   # At least one follow-up sent
    "Interested",    # Prospect expressed interest
    "Meeting Booked",# Discovery call or meeting scheduled
    "Client",        # Converted to paying client
    "Not Interested",# Prospect declined or unresponsive after follow-up
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
        If they don't match, the header is written. Status dropdown validation
        is applied on every call — it is idempotent and ensures new runs always
        have the correct dropdown even if the sheet was set up before this
        feature was added.
        """
        values = self._get_values(f"{self.sheet_name}!A1:{_LAST_COL}1")
        if not values or values[0] != SHEET_COLUMNS:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"{self.sheet_name}!A1:{_LAST_COL}1",
                valueInputOption="RAW",
                body={"values": [SHEET_COLUMNS]},
            ).execute()

        # Apply Status dropdown validation every run (idempotent).
        self.apply_status_dropdown()

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

    def append_prospects(self, prospects: list[dict[str, Any]]) -> None:
        """Append new prospect rows to the bottom of the sheet.

        Uses INSERT_ROWS mode so existing data is never overwritten.
        Rows are written in the order they appear in `prospects`.

        Args:
            prospects: List of enriched prospect dicts (post-deduplication and scoring).
        """
        if not prospects:
            return

        rows = [prospect_to_sheet_row(prospect) for prospect in prospects]
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A:{_LAST_COL}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def apply_status_dropdown(self) -> None:
        """Apply a dropdown validation rule to the Status column for all data rows.

        Uses the Sheets batchUpdate API with a `setDataValidation` request.
        The rule restricts the Status column (column N) to values in
        STATUS_OPTIONS, displayed as a native Google Sheets dropdown.

        The validation covers rows 2–10000 (row 1 is the header). Applying
        this on every run is safe and idempotent — it does not reset existing
        cell values, only updates the validation rule.

        `strict=True` means the Sheets UI will reject manually typed values
        that are not in the list, enforcing workflow consistency.
        """
        sheet_gid = self._get_sheet_gid()
        status_col_index = SHEET_COLUMNS.index("Status")

        request = {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": 1,       # Row 2 (0-indexed) — skip the header
                    "endRowIndex": 10000,     # Cover all foreseeable future rows
                    "startColumnIndex": status_col_index,
                    "endColumnIndex": status_col_index + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": s} for s in STATUS_OPTIONS],
                    },
                    "showCustomUi": True,   # Render as a native Sheets dropdown
                    "strict": True,         # Reject values not in the list
                },
            }
        }

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": [request]},
        ).execute()

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
        prospect.get("status", "New"),
        prospect.get("date_added", ""),
        prospect.get("notes", ""),
        prospect.get("weighted_reputation_score", ""),
    ]
