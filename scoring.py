"""CLI compatibility wrapper for shared prospect scoring helpers.

WHAT: Backwards-compatible root import module.
DOES: Re-exports lead scoring and fit explanation functions from shared.prospecting.
USED_BY: Existing CLI scripts that import `scoring` from the root.
REQUIRES: shared.prospecting.scoring.
"""

from shared.prospecting.scoring import (
    score_prospect,
    weighted_reputation_score,
    why_good_fit,
)

