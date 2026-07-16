"""Lead scoring and fit explanation logic.

IMPORTANT: The lead score is a heuristic, feature-engineered signal.
It is NOT statistically validated, NOT market-tested, and NOT an objective
measure of a business's actual revenue potential or likelihood to convert.

It is a fast, lightweight filter designed to help prioritize which prospects
to review first — not a definitive ranking. Treat it as a starting point
for manual review, not a ground truth.

Scoring Philosophy
------------------
The score is built from observable, publicly available signals:

  - Service-based type:     Businesses are pre-filtered to service categories,
                            so this is a baseline everyone starts with (+2).
  - High-ticket category:   Categories heuristically associated with larger
                            average transaction values (see categories.py).
                            Higher transaction value = greater ROI on digital
                            marketing or CRM investment (+2).
  - Phone present:          A listed phone number suggests the business is
                            active and contactable, slightly improving reach
                            probability (+1).
  - Website status:         Counterintuitively, no website scores HIGHER (+2)
                            than having one (+1). This reflects an outreach
                            opportunity — businesses without websites are
                            stronger candidates for website, SEO, or lead
                            capture services.
  - CRM fit:                Categories where appointment booking, follow-up
                            automation, or customer retention tools have clear
                            utility (+2).
  - Review count >= 25:     A proxy for market validation — at least 25 reviews
                            suggests the business has real volume and an
                            established customer base (+1).

Score range: 1–10 (clamped).

Stronger analytical signals for outreach prioritization
-------------------------------------------------------
Raw data fields often tell a more direct story than the heuristic score:

  - Rating (1–5):          Lower ratings may indicate service gaps your tools
                           could help close; very high ratings signal stability.
  - Review Count:          A proxy for business volume and local market presence.
  - Website present:       Direct indicator of digital maturity.
  - Distance:              Closer businesses may be easier to call on locally
                           or may be part of a geographic campaign cluster.

These raw signals should be considered alongside the lead score when
prioritizing outreach — not treated as inferior to it.

Weighted Reputation Score
-------------------------
Weighted Reputation Score is a separate analytical metric, not a replacement
for Lead Score. It combines review quality (rating) with review confidence
(review volume):

  rating * log10(review_count + 1)

The logarithmic review-count term prevents businesses with massive review
counts from dominating the metric through raw multiplication alone. It reflects
diminishing informational returns: the jump from 0 to 20 reviews is usually
more informative than the jump from 1000 to 1020 reviews.

This is heuristic feature engineering for operational analysis. It is not
formal statistical inference and is not a Google-provided metric.
"""

from __future__ import annotations

import math
from typing import Any

from .utils import safe_float, safe_int


def score_prospect(prospect: dict[str, Any], category: dict[str, Any]) -> int:
    """Compute a heuristic lead score (1–10) for a prospect.

    See module docstring for full explanation of each scoring component.
    The score is intentionally simple and feature-engineered — it is a
    prioritization aid, not a predictive model.

    Args:
        prospect: Enriched prospect dict from google_places.discover_prospects.
        category: Matching category dict from TARGET_CATEGORIES.

    Returns:
        Integer score between 1 and 10 (inclusive).
    """
    score = 0

    # All records in this tool are service businesses — universal baseline.
    score += 2

    # High-ticket categories receive a boost because the ROI on marketing
    # or CRM tools scales with average transaction value. See categories.py
    # for which categories are classified as high_ticket and why.
    if category.get("high_ticket"):
        score += 2

    # A listed phone number is a basic signal of reachability and active status.
    if prospect.get("phone"):
        score += 1

    # No website scores higher than having one — a missing website is an
    # actionable outreach hook (website build, SEO, lead capture opportunity).
    if prospect.get("website"):
        score += 1
    else:
        score += 2

    # CRM-relevant categories benefit from appointment booking, follow-up
    # automation, or customer retention workflows — making our offering a
    # natural fit. See categories.py for crm_fit classification rationale.
    if category.get("crm_fit"):
        score += 2

    # 25+ reviews is a rough threshold for "established local business with
    # real volume" — not a precise cutoff, but a useful heuristic signal.
    if safe_int(prospect.get("review_count")) >= 25:
        score += 1

    return max(1, min(score, 10))


def weighted_reputation_score(prospect: dict[str, Any]) -> float | str:
    """Compute a market-validation reputation confidence metric.

    Formula:
        rating * log10(review_count + 1)

    Returns a float rounded to 2 decimals when rating and review count are
    present. Returns an empty string when either input is missing so the Google
    Sheet cell remains blank instead of implying false precision.
    """
    if prospect.get("rating") in (None, "") or prospect.get("review_count") in (None, ""):
        return ""

    rating = safe_float(prospect.get("rating"))
    review_count = safe_int(prospect.get("review_count"))
    if rating <= 0 or review_count < 0:
        return ""

    # log10(review_count + 1) compresses review volume so very large counts do
    # not overwhelm rating quality. The +1 prevents log10(0) for businesses
    # with zero reviews, producing a valid score of 0 instead of a math error.
    weighted_score = rating * math.log10(review_count + 1)
    return round(weighted_score, 2)


def why_good_fit(prospect: dict[str, Any], category: dict[str, Any]) -> str:
    """Generate a short human-readable explanation of why this prospect is a fit.

    Returns a single sentence based on the dominant signal for this business.
    Priority order: high-ticket + CRM fit > no website > CRM fit alone > general.

    This is intentionally a simplified explanation, not a full analysis.
    It is designed for quick scanning in the Google Sheet's "Why Good Fit" column.
    """
    if category.get("high_ticket") and category.get("crm_fit"):
        return "High-ticket service business where fast lead follow-up matters."

    # No website is the strongest single outreach hook — surfaces it explicitly.
    if not prospect.get("website"):
        return "Strong fit for website, lead capture, and customer inquiry tracking."

    if category.get("crm_fit"):
        return "Likely benefits from appointment booking, CRM, and automated follow-up."

    return "Service-based business that may benefit from better local customer acquisition."
