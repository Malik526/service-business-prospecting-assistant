"""Google Sheets storage client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


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
    "Source",
    "Lead Score",
    "Why Good Fit",
    "Status",
    "Date Added",
    "Notes",
]


class GoogleSheetsClient:
    def __init__(self, sheet_id: str, service_account_file: str, sheet_name: str) -> None:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(
            str(Path(service_account_file).expanduser()),
            scopes=scopes,
        )
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.service = build("sheets", "v4", credentials=credentials)

    def ensure_header(self) -> None:
        values = self._get_values(f"{self.sheet_name}!A1:O1")
        if values and values[0] == SHEET_COLUMNS:
            return

        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A1:O1",
            valueInputOption="RAW",
            body={"values": [SHEET_COLUMNS]},
        ).execute()

    def get_existing_records(self) -> list[dict[str, Any]]:
        self.ensure_header()
        values = self._get_values(f"{self.sheet_name}!A2:O")
        records = []
        for row in values:
            padded = row + [""] * (len(SHEET_COLUMNS) - len(row))
            records.append(dict(zip(SHEET_COLUMNS, padded)))
        return records

    def append_prospects(self, prospects: list[dict[str, Any]]) -> None:
        if not prospects:
            return

        rows = [prospect_to_sheet_row(prospect) for prospect in prospects]
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A:O",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def _get_values(self, sheet_range: str) -> list[list[Any]]:
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=sheet_range,
        ).execute()
        return result.get("values", [])


def prospect_to_sheet_row(prospect: dict[str, Any]) -> list[Any]:
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
        prospect.get("source", ""),
        prospect.get("lead_score", ""),
        prospect.get("why_good_fit", ""),
        prospect.get("status", "New"),
        prospect.get("date_added", ""),
        prospect.get("notes", ""),
    ]
