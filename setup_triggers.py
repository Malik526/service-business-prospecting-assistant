#!/usr/bin/env python3
"""Create weekly Claude Code Remote triggers for batch scraping.

This file exists so the metro batch configs can be registered once in
Claude Code Remote, then run automatically on weekday schedules. It depends on
the Claude Code Remote runtime exposing `claude_code_remote.create_trigger`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from claude_code_remote import create_trigger


PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = "scrape_configs"
SCRAPER_SCRIPT = "run_scraper_parallel.py"


class TriggerDefinition(TypedDict):
    """Describe one scheduled scraper trigger."""

    name: str
    description: str
    cron: str
    batch_config: str


TRIGGERS: tuple[TriggerDefinition, ...] = (
    {
        "name": "MoreClientsCo Batch 1 - West Coast",
        "description": "Weekly: LA, SF, San Diego, Seattle, Denver (5 ZIPs)",
        "cron": "0 9 * * 1",
        "batch_config": f"{CONFIG_DIR}/batch_1_west.json",
    },
    {
        "name": "MoreClientsCo Batch 2 - South TX",
        "description": "Weekly: Houston, Dallas, Austin, San Antonio, Phoenix, Vegas (6 ZIPs)",
        "cron": "0 9 * * 2",
        "batch_config": f"{CONFIG_DIR}/batch_2_south_tx.json",
    },
    {
        "name": "MoreClientsCo Batch 3 - South Atlantic",
        "description": "Weekly: Miami, Tampa, Orlando, Atlanta, Charlotte, Nashville (6 ZIPs)",
        "cron": "0 9 * * 3",
        "batch_config": f"{CONFIG_DIR}/batch_3_south_atlantic.json",
    },
    {
        "name": "MoreClientsCo Batch 4 - Midwest",
        "description": "Weekly: Chicago, Minneapolis, Detroit, Milwaukee, St. Louis (5 ZIPs)",
        "cron": "0 9 * * 4",
        "batch_config": f"{CONFIG_DIR}/batch_4_midwest.json",
    },
    {
        "name": "MoreClientsCo Batch 5 - Mountain",
        "description": "Weekly: Portland, SLC, KC, Indianapolis, Memphis (5 ZIPs)",
        "cron": "0 9 * * 5",
        "batch_config": f"{CONFIG_DIR}/batch_5_mountain.json",
    },
)


def build_trigger_script(batch_config: str) -> str:
    """Build the shell script Claude Code Remote should run for one batch."""
    return f"""#!/bin/bash
set -euo pipefail
cd "{PROJECT_DIR}"
python3 {SCRAPER_SCRIPT} --config {batch_config}
echo "Batch {batch_config} completed at $(date)" >> scraper_runs.log
"""


def validate_setup() -> None:
    """Confirm required scraper files exist before creating remote triggers."""
    missing_files = [
        file_name
        for file_name in (SCRAPER_SCRIPT, *(trigger["batch_config"] for trigger in TRIGGERS))
        if not (PROJECT_DIR / file_name).exists()
    ]

    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(f"Required scraper files are missing: {missing}")


def create_scraper_trigger(trigger_definition: TriggerDefinition) -> dict[str, object]:
    """Create one scheduled trigger for a batch scraping config."""
    return create_trigger(
        name=trigger_definition["name"],
        description=trigger_definition["description"],
        cron=trigger_definition["cron"],
        script=build_trigger_script(trigger_definition["batch_config"]),
    )


def main() -> None:
    """Create all weekday batch triggers and print their IDs."""
    validate_setup()

    print("=" * 80)
    print("Setting up MoreClientsCo autonomous batch scraping triggers...")
    print("=" * 80)
    print("")

    trigger_ids: list[object] = []

    for index, trigger_definition in enumerate(TRIGGERS, 1):
        print(f"[{index}/{len(TRIGGERS)}] Creating trigger: {trigger_definition['name']}")
        trigger = create_scraper_trigger(trigger_definition)
        trigger_id = trigger["id"]
        trigger_ids.append(trigger_id)
        print(f"  Trigger ID: {trigger_id}")
        print(f"  Schedule: {trigger_definition['cron']}")
        print(f"  Batch: {trigger_definition['batch_config']}")
        print("")

    print("=" * 80)
    print("All triggers created successfully")
    print("=" * 80)
    print("")
    print("Trigger IDs:")
    for index, trigger_id in enumerate(trigger_ids, 1):
        print(f"  Batch {index}: {trigger_id}")
    print("")
    print("Next steps:")
    print("  1. Triggers start running on schedule, Monday-Friday at 9 AM.")
    print("  2. Each batch appends scraper results to the configured Google Sheet.")
    print("  3. Monitor runs in the Claude Code Remote dashboard.")


if __name__ == "__main__":
    main()
