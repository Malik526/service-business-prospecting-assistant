"""social.py

Contact and social media URL extractors for the prospecting pipeline.
Takes a business website URL and attempts to:
  - extract_email(): find a publicly listed contact email via mailto: links and
    plain-text pattern matching; falls back to the /contact page if the homepage
    has no address.
  - extract_instagram_url(): find the business Instagram profile link by scanning
    page HTML for any href containing instagram.com/.

Both functions return an empty string on any failure and never raise exceptions.
All HTTP requests are capped at 4 seconds so neither function can stall the pipeline.
Designed to run inside a ThreadPoolExecutor — stateless and safe for parallel calls.

Dependencies:
    - requests >= 2.31.0
"""

from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# Realistic browser-like User-Agent to reduce blocks from bot-detection middleware.
_USER_AGENT = "Mozilla/5.0 (compatible; business-research-bot/1.0)"

# Regex to find any href value containing instagram.com/ — captures the full
# quoted attribute value so we can extract the URL from the surrounding HTML.
_INSTAGRAM_HREF_RE = re.compile(r'href=["\']([^"\']*instagram\.com/[^"\']*)["\']', re.IGNORECASE)


def extract_instagram_url(website_url: str) -> str:
    """Fetch a business website and extract their Instagram URL.

    Scans the page HTML for any link containing instagram.com/.
    Returns the full Instagram profile URL or empty string.

    Args:
        website_url: The business website URL from Google Places.

    Returns:
        Instagram URL string or empty string if not found.
    """
    if not website_url:
        return ""

    website_url = website_url.strip()
    if not website_url.startswith(("http://", "https://")):
        website_url = f"https://{website_url}"

    try:
        response = requests.get(
            website_url,
            timeout=5,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching %s for Instagram URL — skipping.", website_url)
        return ""
    except requests.exceptions.ConnectionError:
        logger.warning("Unreachable: %s — skipping Instagram extraction.", website_url)
        return ""
    except Exception:
        # Any other HTTP or network error should not stop the pipeline.
        return ""

    # --- Extract Instagram href from the page HTML ---
    match = _INSTAGRAM_HREF_RE.search(response.text)
    if not match:
        return ""

    instagram_url = match.group(1).strip()

    # Ensure the URL includes a scheme so it is usable as-is.
    if not instagram_url.startswith("http"):
        instagram_url = "https://" + instagram_url

    # Normalize: remove trailing slashes for consistent formatting.
    instagram_url = instagram_url.rstrip("/")

    return instagram_url


# Hard limit on individual HTTP requests — never wait longer than this.
_EMAIL_TIMEOUT = 4

# Domains whose email addresses are never real business contacts.
_IGNORE_EMAIL_DOMAINS = [
    "sentry.io",
    "wixpress.com",
    "squarespace.com",
    "wordpress.com",
    "example.com",
    "googleapis.com",
    "schema.org",
    "w3.org",
]

# Common non-contact file extensions that can appear next to email-like tokens.
_IGNORE_EMAIL_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".css",
    ".js",
)

# Lightweight page list that catches common contact-page URL conventions.
_EMAIL_FALLBACK_PATHS = ("/contact", "/contact-us", "/about", "/about-us")

# Matches any string that looks like an email address.
_EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"


def extract_email(website_url: str) -> str:
    """Extract a publicly listed contact email from a business website.

    Strategy:
      1. Fetch the homepage — scan for mailto: links first (most reliable),
         then fall back to plain-text email pattern matching.
      2. If no address is found on the homepage, repeat the scan on /contact.
      3. Return the first valid business email found.
      4. Return empty string on any failure.

    Never raises exceptions. Never waits more than 4 seconds per request.

    Args:
        website_url: Business website URL from Google Places.

    Returns:
        Email string or empty string if not found.
    """
    if not website_url:
        return ""

    headers = {"User-Agent": _USER_AGENT}

    def _normalize_url(url: str) -> str:
        """Return a fetchable URL, adding https:// when the scheme is missing."""
        stripped = url.strip()
        if stripped.startswith(("http://", "https://")):
            return stripped
        return f"https://{stripped}"

    def _is_valid_business_email(email: str) -> bool:
        """Return True if the email looks like a real business contact address."""
        lower = email.lower()
        if any(domain in lower for domain in _IGNORE_EMAIL_DOMAINS):
            return False
        if lower.startswith("noreply") or lower.startswith("no-reply"):
            return False
        if lower.endswith(_IGNORE_EMAIL_SUFFIXES):
            return False
        return True

    def _extract_from_html(html: str) -> str:
        """Return the first valid business email found in an HTML string."""
        decoded_html = unescape(html)
        seen = set()

        # mailto: links are the most authoritative — check them first.
        for email in re.findall(r"mailto:(" + _EMAIL_PATTERN + r")", decoded_html):
            email = email.strip().strip(".,;:)")
            if _is_valid_business_email(email):
                return email

        # Fall back to bare email addresses in the page body.
        for email in re.findall(_EMAIL_PATTERN, decoded_html):
            email = email.strip().strip(".,;:)")
            lower = email.lower()
            if lower in seen:
                continue
            seen.add(lower)
            if _is_valid_business_email(email):
                return email
        return ""

    def _fetch_html(url: str) -> str:
        """Fetch a URL and return the response body; empty string on any error."""
        try:
            resp = requests.get(url, timeout=_EMAIL_TIMEOUT, headers=headers, allow_redirects=True)
            return resp.text
        except requests.exceptions.Timeout:
            logger.warning("Timeout fetching %s for email — skipping.", url)
            return ""
        except requests.exceptions.ConnectionError:
            logger.warning("Unreachable: %s — skipping email extraction.", url)
            return ""
        except Exception as exc:
            logger.warning("Email extraction failed for %s: %s", url, exc)
            return ""

    normalized_url = _normalize_url(website_url)

    # --- Homepage and lightweight fallback pages ---
    for page_url in [normalized_url, *[urljoin(normalized_url.rstrip("/") + "/", path) for path in _EMAIL_FALLBACK_PATHS]]:
        html = _fetch_html(page_url)
        email = _extract_from_html(html)
        if email:
            return email

    return ""
