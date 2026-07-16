"""Backend compatibility wrapper for shared search preparation helpers.

WHAT: Preserves the backend import path `prospecting.search`.
DOES: Re-exports address extraction and prospect preparation from shared.prospecting.
USED_BY: FastAPI search endpoint and backend tests.
REQUIRES: shared.prospecting.search.
"""

from shared.prospecting.search import extract_address_components, prepare_new_prospects

