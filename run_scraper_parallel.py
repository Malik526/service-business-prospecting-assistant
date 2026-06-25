#!/usr/bin/env python3
"""Launch multiple prospect scrapers in parallel from scrape_config.json.

This script keeps parallel scraping simple: one JSON file defines the shared
radius, shared category filter, and ZIP codes to run. Each ZIP launches a
separate main.py process. Google Sheets writes are protected by the file lock
inside google_sheets.py.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = "scrape_config.json"
DEFAULT_RADIUS = 20
DEFAULT_CATEGORIES = "electrician,hvac,plumber"
LAUNCH_DELAY_SECONDS = 1


def configure_logging() -> None:
    """Configure plain console logging for launcher progress."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def parse_args(argv: list[str] | None = None) -> Namespace:
    """Parse launcher CLI arguments."""
    parser = ArgumentParser(description="Launch multiple scraper instances in parallel.")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help="Path to scrape config JSON. Defaults to scrape_config.json.",
    )
    return parser.parse_args(argv)


def load_config(config_file: str = DEFAULT_CONFIG_FILE) -> dict[str, Any]:
    """Load scraping configuration from a JSON file."""
    config_path = Path(config_file)
    if not config_path.exists():
        LOGGER.error("Config file not found: %s", config_file)
        raise SystemExit(1)

    try:
        with config_path.open(encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        LOGGER.error("Invalid JSON in %s: %s", config_file, exc)
        raise SystemExit(1) from exc


def validate_config(config: dict[str, Any]) -> tuple[float, str, list[str]]:
    """Return normalized radius, categories, and ZIP list from config."""
    radius = config.get("default_radius", DEFAULT_RADIUS)
    categories = str(config.get("default_categories", DEFAULT_CATEGORIES)).strip()
    zip_codes = config.get("zip_codes", [])

    if not isinstance(zip_codes, list) or not zip_codes:
        LOGGER.error("No ZIP codes found in %s", DEFAULT_CONFIG_FILE)
        raise SystemExit(1)

    normalized_zips = [str(zip_code).strip() for zip_code in zip_codes if str(zip_code).strip()]
    if not normalized_zips:
        LOGGER.error("ZIP code list only contains empty values.")
        raise SystemExit(1)

    if not categories:
        LOGGER.error("default_categories must not be empty.")
        raise SystemExit(1)

    try:
        normalized_radius = float(radius)
    except (TypeError, ValueError) as exc:
        LOGGER.error("default_radius must be numeric: %r", radius)
        raise SystemExit(1) from exc

    return normalized_radius, categories, normalized_zips


def build_command(zip_code: str, radius: float, categories: str) -> list[str]:
    """Build the command for one scraper process."""
    return [
        sys.executable,
        str(PROJECT_DIR / "main.py"),
        "--zip",
        zip_code,
        "--radius",
        str(radius),
        "--categories",
        categories,
    ]


def launch_scraper(zip_code: str, radius: float, categories: str) -> subprocess.Popen[str]:
    """Launch a single scraper instance in the background."""
    command = build_command(zip_code, radius, categories)
    LOGGER.info("Launching scraper for ZIP: %s", zip_code)
    return subprocess.Popen(
        command,
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def log_startup(radius: float, categories: str, zip_codes: list[str]) -> None:
    """Log the launcher configuration before subprocesses start."""
    LOGGER.info("=" * 70)
    LOGGER.info("PARALLEL SCRAPER LAUNCHER")
    LOGGER.info("=" * 70)
    LOGGER.info("Default Radius: %s miles", radius)
    LOGGER.info("Categories: %s", categories)
    LOGGER.info("Total ZIPs to scrape: %d", len(zip_codes))
    LOGGER.info("ZIPs: %s", ", ".join(zip_codes))
    LOGGER.info("=" * 70)
    LOGGER.info("Launching all instances in parallel...")
    LOGGER.info("")


def summarize_processes(processes: list[tuple[str, subprocess.Popen[str]]]) -> tuple[int, int]:
    """Wait for all scraper processes and log their completion status."""
    completed = 0
    failed = 0

    for zip_code, process in processes:
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            LOGGER.info("ZIP %s: Completed successfully", zip_code)
            completed += 1
            continue

        LOGGER.error("ZIP %s: Failed with exit code %s", zip_code, process.returncode)
        if stderr:
            LOGGER.error("ZIP %s stderr: %s", zip_code, stderr[-1000:])
        if stdout:
            LOGGER.error("ZIP %s stdout: %s", zip_code, stdout[-1000:])
        failed += 1

    return completed, failed


def main(argv: list[str] | None = None) -> None:
    """Load config, launch all scraper instances, and report final status."""
    configure_logging()
    args = parse_args(argv)
    config = load_config(args.config)
    radius, categories, zip_codes = validate_config(config)

    log_startup(radius, categories, zip_codes)

    processes = []
    for zip_code in zip_codes:
        processes.append((zip_code, launch_scraper(zip_code, radius, categories)))
        time.sleep(LAUNCH_DELAY_SECONDS)

    LOGGER.info("All %d instances launched in background.", len(zip_codes))
    LOGGER.info("Waiting for all to complete...")
    LOGGER.info("=" * 70)
    LOGGER.info("")

    completed, failed = summarize_processes(processes)

    LOGGER.info("")
    LOGGER.info("=" * 70)
    LOGGER.info("SCRAPING COMPLETE")
    LOGGER.info("=" * 70)
    LOGGER.info("Completed: %d/%d", completed, len(zip_codes))
    if failed:
        LOGGER.info("Failed: %d/%d", failed, len(zip_codes))
    LOGGER.info("=" * 70)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
