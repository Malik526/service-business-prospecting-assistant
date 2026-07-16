"""Backend compatibility wrapper for shared dedupe helpers.

WHAT: Preserves the backend import path `prospecting.dedupe`.
DOES: Re-exports duplicate detection helpers from shared.prospecting.
USED_BY: Backend search preparation.
REQUIRES: shared.prospecting.dedupe.
"""

from shared.prospecting.dedupe import add_to_index, build_dedupe_index, is_duplicate

