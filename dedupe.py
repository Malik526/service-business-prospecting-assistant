"""CLI compatibility wrapper for shared dedupe helpers.

WHAT: Backwards-compatible root import module.
DOES: Re-exports prospect dedupe index helpers from shared.prospecting.
USED_BY: Existing CLI scripts that import `dedupe` from the root.
REQUIRES: shared.prospecting.dedupe.
"""

from shared.prospecting.dedupe import add_to_index, build_dedupe_index, is_duplicate

