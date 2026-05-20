"""Lead scoring and fit explanation rules."""

from __future__ import annotations

from typing import Any

from utils import safe_int


def score_prospect(prospect: dict[str, Any], category: dict[str, Any]) -> int:
    score = 0
    score += 2

    if category.get("high_ticket"):
        score += 2

    if prospect.get("phone"):
        score += 1

    if prospect.get("website"):
        score += 1
    else:
        score += 2

    if category.get("crm_fit"):
        score += 2

    if safe_int(prospect.get("review_count")) >= 25:
        score += 1

    return max(1, min(score, 10))


def why_good_fit(prospect: dict[str, Any], category: dict[str, Any]) -> str:
    if category.get("high_ticket") and category.get("crm_fit"):
        return "High-ticket service business where fast lead follow-up matters."

    if not prospect.get("website"):
        return "Strong fit for website, lead capture, and customer inquiry tracking."

    if category.get("crm_fit"):
        return "Likely benefits from appointment booking, CRM, and automated follow-up."

    return "Service-based business that may benefit from better local customer acquisition."
