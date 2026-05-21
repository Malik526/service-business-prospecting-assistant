"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

DEFAULT_SERVICE_ACCOUNT_FILE = "./credentials/service-account.json"


@dataclass(frozen=True)
class Config:
    google_places_api_key: str
    google_sheet_id: str
    google_service_account_file: str
    anthropic_api_key: str
    sheet_name: str = "Prospects"
    max_pages_per_category: int = 3


def load_config() -> Config:
    return Config(
        google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY", "").strip(),
        google_sheet_id=os.getenv("GOOGLE_SHEET_ID", "").strip(),
        google_service_account_file=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            DEFAULT_SERVICE_ACCOUNT_FILE,
        ).strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Prospects").strip() or "Prospects",
        max_pages_per_category=int(os.getenv("MAX_PAGES_PER_CATEGORY", "3")),
    )


def validate_config(config: Config) -> None:
    missing = []
    if not config.google_places_api_key:
        missing.append("GOOGLE_PLACES_API_KEY")
    if not config.google_sheet_id:
        missing.append("GOOGLE_SHEET_ID")
    if not config.google_service_account_file:
        missing.append("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not config.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    service_account_path = Path(config.google_service_account_file).expanduser()
    if not service_account_path.exists():
        raise FileNotFoundError(
            "GOOGLE_SERVICE_ACCOUNT_FILE does not exist: "
            f"{service_account_path}"
        )
