"""Backend compatibility wrapper for shared utility helpers.

WHAT: Preserves the backend import path `prospecting.utils`.
DOES: Re-exports normalization, conversion, and distance helpers from shared.prospecting.
USED_BY: Backend compatibility modules and shared prospect preparation code.
REQUIRES: shared.prospecting.utils.
"""

from shared.prospecting.utils import (
    MILES_TO_METERS,
    clean_phone,
    haversine_distance,
    miles_to_meters,
    normalize_text,
    normalize_website,
    safe_float,
    safe_int,
    today_iso,
)

