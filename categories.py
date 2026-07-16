"""CLI compatibility wrapper for shared prospect category helpers.

WHAT: Backwards-compatible root import module.
DOES: Re-exports target categories and filtering helpers from shared.prospecting.
USED_BY: Existing CLI scripts and tests that import `categories` from the root.
REQUIRES: shared.prospecting.categories.
"""

from shared.prospecting.categories import (
    TARGET_CATEGORIES,
    filter_target_categories,
    normalize_category_key,
)

