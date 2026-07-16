"""Backend compatibility wrapper for shared scoring helpers.

WHAT: Preserves the backend import path `prospecting.scoring`.
DOES: Re-exports scoring and fit explanation functions from shared.prospecting.
USED_BY: Backend search preparation and API response enrichment.
REQUIRES: shared.prospecting.scoring.
"""

from shared.prospecting.scoring import (
    score_prospect,
    weighted_reputation_score,
    why_good_fit,
)

