"""Tests for backend prospect preparation.

These tests avoid network and AWS calls by exercising only the pure
deduplication/scoring preparation layer.
"""

from unittest import TestCase

from prospecting.categories import filter_target_categories
from prospecting.search import prepare_new_prospects


class SearchPreparationTest(TestCase):
    """Test case for backend prospect preparation behavior."""

    def test_prepare_new_prospects_scores_and_dedupes(self) -> None:
        """Verify duplicate records are skipped and new prospects are scored."""
        categories = filter_target_categories("electrician")
        raw_prospects = [
            {
                "place_id": "new-place",
                "business_name": "Bright Wire Electric",
                "category": "electricians",
                "address": "1 Main St, Queens, NY",
                "phone": "(555) 111-2222",
                "website": "",
                "rating": 4.8,
                "review_count": 35,
                "distance_miles": 3.4,
                "address_components": [],
                "source": "Google Places API",
            },
            {
                "place_id": "old-place",
                "business_name": "Existing Electric",
                "category": "electricians",
                "address": "2 Main St, Queens, NY",
                "phone": "(555) 333-4444",
                "website": "https://existing.example",
                "rating": 4.2,
                "review_count": 12,
                "distance_miles": 5.1,
                "address_components": [],
                "source": "Google Places API",
            },
        ]
        existing_records = [{"place_id": "old-place"}]

        prospects, duplicate_count = prepare_new_prospects(
            raw_prospects=raw_prospects,
            selected_categories=categories,
            existing_records=existing_records,
            search_zip="11385",
            search_radius=20,
        )

        self.assertEqual(duplicate_count, 1)
        self.assertEqual(len(prospects), 1)
        self.assertEqual(prospects[0]["place_id"], "new-place")
        self.assertEqual(prospects[0]["lead_score"], 10)
        self.assertEqual(prospects[0]["search_zip"], "11385")
