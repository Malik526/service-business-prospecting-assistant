"""Tests for scraper email validation and extraction filtering.

These tests keep network calls mocked while verifying fake email rejection,
legitimate business email acceptance, fallback behavior, and summary counters.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pipeline.email_validation import (
    get_email_validation_stats,
    is_fake_email,
    reset_email_validation_stats,
    validate_email_list,
)
from pipeline.social import extract_email


class EmailValidationTests(unittest.TestCase):
    """Validate fake email filtering without live website requests."""

    def setUp(self) -> None:
        """Reset validation counters before each test."""
        reset_email_validation_stats()

    def test_rejects_known_fake_email_patterns(self) -> None:
        """Reject placeholder domains, file-name matches, and test emails."""
        fake_emails = [
            "user@domain.com",
            "your@realbusiness.com",
            "youremail@realbusiness.com",
            "yourname@realbusiness.com",
            "info@mysite.com",
            "header@2x.jpg",
            "example@domain.com",
            "test@domain.com",
            "contact@domain.com",
            "noreply@realbusiness.com",
        ]

        for email in fake_emails:
            with self.subTest(email=email):
                self.assertTrue(is_fake_email(email))

    def test_accepts_legitimate_generic_business_email(self) -> None:
        """Accept common mailbox names when they use a real business domain."""
        self.assertFalse(is_fake_email("info@grimascleaningservice.com"))

    def test_validate_email_list_returns_first_valid_email(self) -> None:
        """Skip fake candidates and return the first legitimate email."""
        email, rejected = validate_email_list(
            [
                "user@domain.com",
                "header@2x.jpg",
                "info@grimascleaningservice.com",
            ]
        )

        self.assertEqual(email, "info@grimascleaningservice.com")
        self.assertEqual(rejected, 2)

    def test_extract_email_falls_back_after_fake_homepage_email(self) -> None:
        """Try fallback pages when the homepage only exposes fake emails."""
        responses = [
            type("Response", (), {"text": "Contact us at user@domain.com"})(),
            type("Response", (), {"text": "Email mailto:info@grimascleaningservice.com"})(),
        ]

        with patch("pipeline.social.requests.get", side_effect=responses) as get_mock:
            email = extract_email("https://grimascleaningservice.com")

        self.assertEqual(email, "info@grimascleaningservice.com")
        self.assertEqual(get_mock.call_count, 2)
        self.assertIn("/contact", get_mock.call_args.args[0])

        stats = get_email_validation_stats()
        self.assertEqual(stats["emails_validated"], 1)
        self.assertEqual(stats["emails_rejected"], 1)


if __name__ == "__main__":
    unittest.main()
