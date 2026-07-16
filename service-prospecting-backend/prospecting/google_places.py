"""Backend compatibility wrapper for the shared Google Places client.

WHAT: Preserves the backend import path `prospecting.google_places`.
DOES: Re-exports Google Places discovery constants and client from shared.prospecting.
USED_BY: FastAPI search endpoint.
REQUIRES: shared.prospecting.google_places and backend GOOGLE_PLACES_API_KEY.
"""

from shared.prospecting.google_places import (
    DETAILS_URL,
    GEOCODE_URL,
    TEXT_SEARCH_URL,
    GooglePlacesClient,
)
from shared.prospecting.google_places import requests
