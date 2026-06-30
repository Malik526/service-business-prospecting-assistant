"""Email validation helpers for contact extraction.

This module centralizes fake and placeholder email detection so the scraper
keeps only likely business contact addresses before writing prospect data.
It also exposes lightweight thread-safe counters for run summaries.
"""

from __future__ import annotations

import re
from threading import Lock


FAKE_EMAIL_PATTERNS = {
    "placeholder_domains": [
        "domain.com",
        "example.com",
        "test.com",
        "yoursite.com",
        "mysite.com",
        "website.com",
        "business.com",
        "company.com",
        "sample.com",
        "yourdomain.com",
        "yourwebsite.com",
    ],
    "always_placeholder_usernames": [
        "user",
        "test",
        "example",
        "email",
        "mail",
        "placeholder",
        "guest",
        "demo",
    ],
    "generic_contact_usernames": [
        "admin",
        "contact",
        "hello",
        "info",
        "support",
        "webmaster",
    ],
    "test_name_patterns": [
        r"john\.doe@",
        r"jane\.doe@",
        r"john_doe@",
        r"jane_smith@",
        r"test\.user@",
        r"demo\.user@",
    ],
    "file_extensions": [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".pdf",
        ".doc",
        ".docx",
        ".css",
        ".js",
    ],
    "auto_generated": [
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
        "automated",
        "notification",
    ],
    "platform_domains": [
        "sentry.io",
        "wixpress.com",
        "squarespace.com",
        "wordpress.com",
        "googleapis.com",
        "schema.org",
        "w3.org",
    ],
}

_TEST_NAME_RE = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in FAKE_EMAIL_PATTERNS["test_name_patterns"]
]
_STATS_LOCK = Lock()
_EMAIL_VALIDATION_STATS = {
    "emails_validated": 0,
    "emails_rejected": 0,
}


def _split_email(email: str) -> tuple[str, str]:
    """Split an email into lowercase local and domain parts."""
    local, _, domain = email.lower().strip().partition("@")
    return local, domain


def is_fake_email(email: str) -> bool:
    """Return True when an email matches fake, placeholder, or unusable patterns."""
    if not email or not isinstance(email, str):
        return True

    email_lower = email.lower().strip().strip(".,;:)")
    local_part, domain = _split_email(email_lower)
    if not local_part or not domain or "." not in domain:
        return True

    if any(extension in email_lower for extension in FAKE_EMAIL_PATTERNS["file_extensions"]):
        return True

    if domain in FAKE_EMAIL_PATTERNS["platform_domains"]:
        return True

    placeholder_domain = domain in FAKE_EMAIL_PATTERNS["placeholder_domains"]
    if placeholder_domain:
        return True

    if local_part in FAKE_EMAIL_PATTERNS["always_placeholder_usernames"]:
        return True

    if local_part in FAKE_EMAIL_PATTERNS["auto_generated"]:
        return True

    if any(pattern.search(email_lower) for pattern in _TEST_NAME_RE):
        return True

    return False


def validate_email_list(emails: list[str]) -> tuple[str, int]:
    """Return the first valid email and the number of rejected candidates."""
    rejected = 0
    seen = set()

    for raw_email in emails:
        email = str(raw_email).strip().strip(".,;:)")
        email_lower = email.lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)

        if is_fake_email(email):
            rejected += 1
            continue

        return email, rejected

    return "", rejected


def reset_email_validation_stats() -> None:
    """Reset run-level email validation counters."""
    with _STATS_LOCK:
        _EMAIL_VALIDATION_STATS["emails_validated"] = 0
        _EMAIL_VALIDATION_STATS["emails_rejected"] = 0


def record_email_validation_result(accepted: bool, rejected_count: int) -> None:
    """Add one extraction result to the run-level validation counters."""
    with _STATS_LOCK:
        if accepted:
            _EMAIL_VALIDATION_STATS["emails_validated"] += 1
        _EMAIL_VALIDATION_STATS["emails_rejected"] += max(0, rejected_count)


def get_email_validation_stats() -> dict[str, int | float]:
    """Return a copy of email validation counters with fake-rate percentage."""
    with _STATS_LOCK:
        stats = dict(_EMAIL_VALIDATION_STATS)

    total = stats["emails_validated"] + stats["emails_rejected"]
    stats["fake_email_rate"] = round((stats["emails_rejected"] / total * 100), 1) if total else 0
    return stats
