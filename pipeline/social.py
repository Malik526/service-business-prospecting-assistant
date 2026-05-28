"""social.py

Social media URL extractor for the prospecting pipeline.
Takes a business website URL and attempts to find their Instagram profile
link by scanning the page HTML.

Returns Instagram URL if found, empty string if not.
Handles timeouts and errors gracefully — never crashes the pipeline if a
site is unreachable.

Dependencies:
    - requests >= 2.31.0
"""

# Instagram URL extraction is currently disabled in the main pipeline due to
# performance impact at scale. Re-enable when processing volume justifies it.
# To re-enable: import and call extract_instagram_url() in main.py after
# prospect enrichment.

from __future__ import annotations

import logging
import re

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
