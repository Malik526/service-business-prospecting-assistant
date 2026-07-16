"""Backend compatibility wrapper for shared category helpers.

WHAT: Preserves the backend import path `prospecting.categories`.
DOES: Re-exports category definitions and filters from shared.prospecting.
USED_BY: FastAPI endpoints and backend unit tests.
REQUIRES: shared.prospecting.categories.
"""

from shared.prospecting.categories import (
    TARGET_CATEGORIES,
    filter_target_categories,
    normalize_category_key,
)

