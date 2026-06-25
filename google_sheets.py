"""Google Sheets storage client.

This module handles all interaction with the Google Sheets API:
  - Reading row 1 and building a dynamic PROSPECTS column map.
  - Caching the live schema in config/PROSPECTS_SCHEMA.json.
  - Applying dropdown validation to controlled outreach columns.
  - Reading existing records for deduplication.
  - Appending new prospect rows.

Authentication uses a service account (not OAuth user login). The Google Sheet
must be shared with the service account email as an Editor — without this,
reads and writes will fail with a 403 permission error even if authentication
itself succeeds.

The default PROSPECTS schema is still defined here, but runtime reads never
assume the columns are in that order. If the user rearranges columns in the
sheet, row serialization, duplicate checks, and dropdown validation follow the
live header mapping.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
SCHEMA_CACHE_PATH = (
    Path(__file__).resolve().parent / "config" / "PROSPECTS_SCHEMA.json"
)

# Ordered list of column headers. The order here defines the column layout in
# a new empty Google Sheet. Existing sheets may be rearranged.
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
    "Street",                 # Column V — street from Google address_components
    "City",                   # Column W — city from Google address_components
    "State",                  # Column X — state from Google address_components
    "ZIP",                    # Column Y — ZIP from Google address_components
]

ADDRESS_COMPONENT_COLUMNS = ["Street", "City", "State", "ZIP"]

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

PROSPECT_FIELD_TO_COLUMN = {
    "place_id": "Place ID",
    "business_name": "Business Name",
    "category": "Category",
    "address": "Address",
    "phone": "Phone",
    "website": "Website",
    "google_maps_url": "Google Maps URL",
    "rating": "Rating",
    "review_count": "Review Count",
    "distance_miles": "Distance From Search ZIP (mi)",
    "source": "Source",
    "lead_score": "Lead Score",
    "why_good_fit": "Why Good Fit",
    "status": "Status",
    "last_contact_date": "Last Contact Date",
    "last_outcome": "Last Outcome",
    "notes": "Notes",
    "search_zip": "Search ZIP Code",
    "search_radius": "Search Radius (mi)",
    "instagram_url": "Instagram URL",
    "email": "Email",
    "street": "Street",
    "city": "City",
    "state": "State",
    "zip": "ZIP",
}


@dataclass(frozen=True)
class SheetSchema:
    """Live header metadata for the PROSPECTS sheet."""

    schema_version: int
    last_updated: str
    headers: list[str]
    columns: dict[str, int]


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
        self._schema: SheetSchema | None = None

    def ensure_header(self) -> SheetSchema:
        """Ensure row 1 exists, verify the cached schema, and apply validation.

        This method remains the public setup entrypoint for callers that used
        the older fixed-column implementation. It now returns the live schema.
        """
        schema = self.get_schema(force_refresh=True)
        self.apply_dropdown_validations(schema=schema)
        return schema

    def get_schema(self, force_refresh: bool = False) -> SheetSchema:
        """Read row 1, compare it to the schema cache, and return live mapping."""
        if self._schema is not None and not force_refresh:
            return self._schema

        cached_schema = self._load_schema_cache()
        headers = self.read_header_row()

        if not headers:
            headers = SHEET_COLUMNS[:]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=(
                    f"{self.sheet_name}!A1:"
                    f"{column_index_to_letter(len(headers) - 1)}1"
                ),
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()
            logger.info("Created default PROSPECTS header row.")

        headers = self._ensure_address_component_headers(headers)
        schema = build_schema(headers)
        missing_columns = [
            column for column in SHEET_COLUMNS if column not in schema.columns
        ]
        if missing_columns:
            logger.warning(
                "PROSPECTS sheet is missing expected column(s): %s. "
                "Operations for missing columns will be skipped.",
                ", ".join(missing_columns),
            )

        if cached_schema is None:
            logger.info("No PROSPECTS schema cache found; creating %s.", SCHEMA_CACHE_PATH)
            self._save_schema_cache(schema)
        elif cached_schema.columns != schema.columns:
            logger.warning(
                "PROSPECTS schema changed. Updating cache at %s.",
                SCHEMA_CACHE_PATH,
            )
            self._save_schema_cache(schema)
        else:
            schema = cached_schema

        self._schema = schema
        return schema

    def read_header_row(self) -> list[str]:
        """Read row 1 from the live sheet and return trimmed header cells."""
        values = self._get_values(f"{self.sheet_name}!1:1")
        if not values:
            return []
        headers = [str(value).strip() for value in values[0]]
        while headers and not headers[-1]:
            headers.pop()
        return headers

    def _ensure_address_component_headers(self, headers: list[str]) -> list[str]:
        """Append required address component headers when an existing sheet lacks them."""
        missing_headers = [
            header for header in ADDRESS_COMPONENT_COLUMNS if header not in headers
        ]
        if not missing_headers:
            return headers

        start_index = len(headers)
        updated_headers = headers + missing_headers
        start_col = column_index_to_letter(start_index)
        end_col = column_index_to_letter(len(updated_headers) - 1)
        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!{start_col}1:{end_col}1",
            valueInputOption="RAW",
            body={"values": [missing_headers]},
        ).execute()
        logger.info(
            "Added address component header column(s): %s.",
            ", ".join(missing_headers),
        )
        return updated_headers

    def get_existing_records(self) -> list[dict[str, Any]]:
        """Read all existing data rows from the sheet and return as a list of dicts.

        Called at the start of each run to build the deduplication index.
        Rows are keyed by the live header names, so column reordering does not
        affect downstream record access.

        Returns:
            List of dicts keyed by current row-1 header values.
        """
        schema = self.ensure_header()
        values = self.get_data_rows(schema)
        records = []
        for row in values:
            # Pad short rows so every dict has the full set of live headers.
            padded = row + [""] * (len(schema.headers) - len(row))
            records.append(dict(zip(schema.headers, padded)))
        return records

    def get_data_rows(self, schema: SheetSchema | None = None) -> list[list[Any]]:
        """Read data rows through the last live header column."""
        schema = schema or self.get_schema()
        if not schema.headers:
            return []
        last_col = column_index_to_letter(len(schema.headers) - 1)
        return self._get_values(f"{self.sheet_name}!A2:{last_col}")

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

        schema = self.ensure_header()
        existing_place_ids = self.get_existing_place_ids(schema)

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

        rows = [prospect_to_sheet_row(prospect, schema) for prospect in appendable]
        last_col = column_index_to_letter(len(schema.headers) - 1)
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A:{last_col}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

        self.apply_dropdown_validations(schema=schema)
        logger.info(
            "Appended %d prospect(s). Skipped %d duplicate Place ID(s).",
            len(appendable),
            skipped_duplicates,
        )
        return {"appended": len(appendable), "skipped_duplicates": skipped_duplicates}

    def get_existing_place_ids(self, schema: SheetSchema | None = None) -> set[str]:
        """Return existing Place IDs using the live Place ID column mapping."""
        schema = schema or self.get_schema()
        place_id_index = schema.columns.get("Place ID")
        if place_id_index is None:
            logger.warning("Cannot dedupe by Place ID because the column is missing.")
            return set()

        col_letter = column_index_to_letter(place_id_index)
        rows = self._get_values(f"{self.sheet_name}!{col_letter}2:{col_letter}")
        return {
            str(row[0]).strip()
            for row in rows
            if row and str(row[0]).strip()
        }

    def apply_dropdown_validations(self, schema: SheetSchema | None = None) -> None:
        """Apply dropdown validation rules to controlled PROSPECTS columns.

        Uses the Sheets batchUpdate API with a `setDataValidation` request.
        Rules are applied to Status and Last Outcome for rows 2-10000.

        The validation covers rows 2–10000 (row 1 is the header). Applying
        this on every run is safe and idempotent — it does not reset existing
        cell values, only updates the validation rule.

        `strict=False` keeps the dropdown suggestions visible while allowing
        manual values that are not in the configured list.
        """
        schema = schema or self.get_schema()
        sheet_gid = self._get_sheet_gid()
        requests = []
        for column_name, options in {
            "Status": STATUS_OPTIONS,
            "Last Outcome": LAST_OUTCOME_OPTIONS,
        }.items():
            request = self._validation_request(
                sheet_gid=sheet_gid,
                column_name=column_name,
                options=options,
                schema=schema,
            )
            if request is not None:
                requests.append(request)

        if not requests:
            logger.warning("No dropdown validations applied; controlled columns are missing.")
            return

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": requests},
        ).execute()

    def _validation_request(
        self,
        sheet_gid: int,
        column_name: str,
        options: list[str],
        schema: SheetSchema,
    ) -> dict[str, Any] | None:
        """Build one Google Sheets data-validation request for a dropdown column."""
        column_index = schema.columns.get(column_name)
        if column_index is None:
            logger.warning(
                "Skipping dropdown validation; '%s' column is missing.",
                column_name,
            )
            return None
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

    def _load_schema_cache(self) -> SheetSchema | None:
        """Load the cached PROSPECTS schema from disk if it exists and is valid."""
        if not SCHEMA_CACHE_PATH.exists():
            return None
        try:
            with open(SCHEMA_CACHE_PATH, encoding="utf-8") as schema_file:
                data = json.load(schema_file)
        except Exception as exc:
            logger.warning("Could not read schema cache: %s", exc)
            return None

        try:
            columns = {
                str(column): int(index)
                for column, index in data.get("columns", {}).items()
            }
            headers = data.get("headers") or headers_from_mapping(columns)
            return SheetSchema(
                schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
                last_updated=str(data.get("last_updated", "")),
                headers=[str(header) for header in headers],
                columns=columns,
            )
        except Exception as exc:
            logger.warning("Schema cache is invalid and will be rebuilt: %s", exc)
            return None

    def _save_schema_cache(self, schema: SheetSchema) -> None:
        """Persist the live schema cache to config/PROSPECTS_SCHEMA.json."""
        SCHEMA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": schema.schema_version,
            "last_updated": datetime.now(timezone.utc).date().isoformat(),
            "columns": schema.columns,
            "headers": schema.headers,
        }
        with open(SCHEMA_CACHE_PATH, "w", encoding="utf-8") as schema_file:
            json.dump(payload, schema_file, indent=2)
            schema_file.write("\n")


def build_schema(headers: list[str]) -> SheetSchema:
    """Build a SheetSchema from row-1 headers, preserving live indexes."""
    columns: dict[str, int] = {}
    duplicates = []
    for index, header in enumerate(headers):
        if not header:
            continue
        if header in columns:
            duplicates.append(header)
            continue
        columns[header] = index

    if duplicates:
        logger.warning(
            "Duplicate header(s) found in PROSPECTS sheet and ignored after first use: %s.",
            ", ".join(sorted(set(duplicates))),
        )

    return SheetSchema(
        schema_version=SCHEMA_VERSION,
        last_updated=datetime.now(timezone.utc).date().isoformat(),
        headers=headers,
        columns=columns,
    )


def headers_from_mapping(columns: dict[str, int]) -> list[str]:
    """Rebuild a sparse header list from a cached column mapping."""
    if not columns:
        return []
    headers = [""] * (max(columns.values()) + 1)
    for header, index in columns.items():
        headers[index] = header
    return headers


def column_index_to_letter(index: int) -> str:
    """Convert a zero-based column index to a Google Sheets column letter."""
    if index < 0:
        raise ValueError("Column index must be non-negative.")
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def prospect_to_sheet_row(
    prospect: dict[str, Any],
    schema: SheetSchema | None = None,
) -> list[Any]:
    """Serialize a prospect dict into an ordered list of cell values.

    Values are placed by live header mapping when a schema is provided. Missing
    sheet columns are skipped so deleted columns fail gracefully.
    """
    schema = schema or build_schema(SHEET_COLUMNS)
    row = [""] * len(schema.headers)
    for field_name, column_name in PROSPECT_FIELD_TO_COLUMN.items():
        column_index = schema.columns.get(column_name)
        if column_index is None:
            continue
        value = prospect.get(field_name, "")
        if field_name == "status":
            value = value or "New"
        row[column_index] = value
    return row
