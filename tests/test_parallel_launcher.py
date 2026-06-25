"""Tests for the parallel scraper launcher.

These tests keep subprocess launches mocked so the suite never calls Google APIs
or writes to the live prospect sheet.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import run_scraper_parallel


class ParallelLauncherTests(unittest.TestCase):
    """Validate config loading, command construction, and launcher flow."""

    def test_load_config_reads_json_file(self) -> None:
        """Load a scrape config JSON file from disk."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "scrape_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "default_radius": 5,
                        "default_categories": "electrician",
                        "zip_codes": ["11375"],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_scraper_parallel.load_config(str(config_path)),
                {
                    "default_radius": 5,
                    "default_categories": "electrician",
                    "zip_codes": ["11375"],
                },
            )

    def test_validate_config_normalizes_values(self) -> None:
        """Normalize radius, category, and ZIP values from config."""
        radius, categories, zip_codes = run_scraper_parallel.validate_config(
            {
                "default_radius": "10",
                "default_categories": " electrician,hvac ",
                "zip_codes": [11375, " 07032 "],
            }
        )

        self.assertEqual(radius, 10.0)
        self.assertEqual(categories, "electrician,hvac")
        self.assertEqual(zip_codes, ["11375", "07032"])

    def test_build_command_targets_main_cli(self) -> None:
        """Build a main.py scraper command with ZIP, radius, and categories."""
        command = run_scraper_parallel.build_command("11375", 5.0, "electrician,hvac")

        self.assertEqual(Path(command[1]).name, "main.py")
        self.assertEqual(
            command[2:],
            ["--zip", "11375", "--radius", "5.0", "--categories", "electrician,hvac"],
        )

    def test_launch_scraper_uses_nonblocking_popen(self) -> None:
        """Launch one scraper with subprocess.Popen and captured output."""
        fake_process = MagicMock()
        with patch("run_scraper_parallel.subprocess.Popen", return_value=fake_process) as popen_mock:
            process = run_scraper_parallel.launch_scraper("11375", 5.0, "electrician")

        self.assertIs(process, fake_process)
        popen_mock.assert_called_once()
        self.assertEqual(Path(popen_mock.call_args.args[0][1]).name, "main.py")
        self.assertEqual(popen_mock.call_args.kwargs["cwd"], run_scraper_parallel.PROJECT_DIR)
        self.assertEqual(popen_mock.call_args.kwargs["stdout"], run_scraper_parallel.subprocess.PIPE)
        self.assertEqual(popen_mock.call_args.kwargs["stderr"], run_scraper_parallel.subprocess.PIPE)

    def test_parse_instance_stats_reads_scraping_stats_line(self) -> None:
        """Parse one machine-readable stats line from child stderr."""
        stderr = (
            "some warning\n"
            'SCRAPING_STATS:{"total_prospects": 3, "emails_found": 1}\n'
        )

        stats = run_scraper_parallel.parse_instance_stats(stderr)

        self.assertEqual(stats, {"total_prospects": 3, "emails_found": 1})

    def test_parse_instance_stats_returns_none_without_valid_json(self) -> None:
        """Ignore stderr that has no parseable SCRAPING_STATS payload."""
        self.assertIsNone(run_scraper_parallel.parse_instance_stats("plain stderr"))
        self.assertIsNone(run_scraper_parallel.parse_instance_stats("SCRAPING_STATS:{bad json}"))

    def test_aggregate_stats_sums_instances_and_percentages(self) -> None:
        """Aggregate counts and recalculate capture percentages."""
        aggregated = run_scraper_parallel.aggregate_stats(
            [
                {
                    "total_prospects": 4,
                    "by_category": {"electrician": 2, "hvac": 1, "plumber": 1},
                    "emails_found": 2,
                    "emails_by_category": {"electrician": 1, "hvac": 1, "plumber": 0},
                    "instagrams_found": 1,
                    "instagrams_by_category": {"electrician": 1, "hvac": 0, "plumber": 0},
                },
                {
                    "total_prospects": 6,
                    "by_category": {"electrician": 1, "hvac": 2, "plumber": 3},
                    "emails_found": 3,
                    "emails_by_category": {"electrician": 0, "hvac": 1, "plumber": 2},
                    "instagrams_found": 2,
                    "instagrams_by_category": {"electrician": 0, "hvac": 1, "plumber": 1},
                },
            ]
        )

        self.assertEqual(aggregated["total_prospects"], 10)
        self.assertEqual(aggregated["by_category"], {"electrician": 3, "hvac": 3, "plumber": 4})
        self.assertEqual(aggregated["emails_found"], 5)
        self.assertEqual(aggregated["emails_captured_percent"], 50.0)
        self.assertEqual(aggregated["instagrams_found"], 3)
        self.assertEqual(aggregated["instagrams_captured_percent"], 30.0)

    def test_summarize_processes_collects_stats(self) -> None:
        """Collect child-process stats alongside completion counts."""
        process = MagicMock()
        process.returncode = 0
        process.communicate.return_value = (
            "",
            'SCRAPING_STATS:{"total_prospects": 2, "emails_found": 1}',
        )

        completed, failed, stats_list = run_scraper_parallel.summarize_processes(
            [("11375", process)]
        )

        self.assertEqual(completed, 1)
        self.assertEqual(failed, 0)
        self.assertEqual(stats_list, [{"total_prospects": 2, "emails_found": 1}])

    def test_main_launches_all_before_waiting(self) -> None:
        """Launch all ZIPs before summarize waits on process completion."""
        events = []

        def fake_launch(zip_code: str, radius: float, categories: str) -> MagicMock:
            """Record launch order and return a fake process."""
            events.append(("launch", zip_code))
            return MagicMock()

        def fake_summarize(processes: list[tuple[str, MagicMock]]) -> tuple[int, int, list[dict]]:
            """Record summarize timing after all launches."""
            events.append(("summarize", ",".join(zip_code for zip_code, _ in processes)))
            return len(processes), 0, [
                {
                    "total_prospects": 0,
                    "by_category": {"electrician": 0, "hvac": 0, "plumber": 0},
                    "emails_found": 0,
                    "emails_by_category": {"electrician": 0, "hvac": 0, "plumber": 0},
                    "instagrams_found": 0,
                    "instagrams_by_category": {"electrician": 0, "hvac": 0, "plumber": 0},
                }
            ]

        with patch(
            "run_scraper_parallel.load_config",
            return_value={
                "default_radius": 5,
                "default_categories": "electrician",
                "zip_codes": ["11375", "07032", "10001"],
            },
        ), patch("run_scraper_parallel.launch_scraper", side_effect=fake_launch), patch(
            "run_scraper_parallel.summarize_processes",
            side_effect=fake_summarize,
        ), patch("run_scraper_parallel.print_final_summary") as summary_mock, patch(
            "run_scraper_parallel.time.sleep"
        ) as sleep_mock:
            run_scraper_parallel.main([])

        self.assertEqual(
            events,
            [
                ("launch", "11375"),
                ("launch", "07032"),
                ("launch", "10001"),
                ("summarize", "11375,07032,10001"),
            ],
        )
        self.assertEqual(sleep_mock.call_count, 3)
        sleep_mock.assert_called_with(run_scraper_parallel.LAUNCH_DELAY_SECONDS)
        summary_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
