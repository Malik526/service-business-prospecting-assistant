"""CLI compatibility wrapper for the shared Google Places client.

WHAT: Backwards-compatible root import module.
DOES: Re-exports Google Places discovery constants and client from shared.prospecting.
USED_BY: Existing CLI scripts and tests that import `google_places` from the root.
REQUIRES: shared.prospecting.google_places and GOOGLE_PLACES_API_KEY from CLI config.
"""

from shared.prospecting.google_places import (
    DETAILS_URL,
    GEOCODE_URL,
    TEXT_SEARCH_URL,
    GooglePlacesClient,
)
from shared.prospecting.google_places import requests
