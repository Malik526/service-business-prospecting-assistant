"""Google Places and Geocoding API client.

This module handles all communication with two Google APIs:
  - Geocoding API: converts a ZIP code into geographic coordinates (lat/lng).
  - Places API (Text Search + Place Details): finds businesses by category
    within a radius and fetches enriched details for each result.

Pagination
----------
Google Places Text Search returns up to 20 results per page. When more results
exist, the response includes a `next_page_token`. Passing this token as
`pagetoken` in the next request fetches the next page. There is a mandatory
~2-second propagation delay before a token is usable — that is why this module
sleeps 2 seconds between paginated requests. `max_pages_per_category` caps how
many pages are fetched per category to control API usage and billing.

Distance
--------
Each prospect includes a `distance_miles` field calculated via the Haversine
formula (see utils.py). The search origin (ZIP centroid) is retained in memory
during a `discover_prospects` call and compared against each business's
geometry returned by the Text Search response.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from utils import haversine_distance, miles_to_meters


GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


class GooglePlacesClient:
    def __init__(self, api_key: str, max_pages_per_category: int = 3) -> None:
        self.api_key = api_key
        self.max_pages_per_category = max_pages_per_category

    def zip_to_location(self, zip_code: str) -> tuple[float, float]:
        """Convert a US ZIP code into (latitude, longitude) via the Geocoding API.

        Uses both `address` and `components` parameters to improve result
        accuracy — the `components` filter pins the result to US postal codes
        and reduces false matches for ambiguous ZIP codes.

        Raises:
            RuntimeError: if the API returns a non-OK status.
            ValueError: if no geocoding result is found for the ZIP.
        """
        response = requests.get(
            GEOCODE_URL,
            params={
                "address": zip_code,
                # components filter improves accuracy for ambiguous ZIPs
                "components": f"postal_code:{zip_code}|country:US",
                "key": self.api_key,
            },
            timeout=30,
        )
        payload = self._parse_response(response)
        results = payload.get("results", [])
        if not results:
            raise ValueError(f"No location found for ZIP code {zip_code}")

        location = results[0]["geometry"]["location"]
        return location["lat"], location["lng"]

    def search_category(
        self,
        category: dict[str, Any],
        latitude: float,
        longitude: float,
        radius_miles: float,
    ) -> list[dict[str, Any]]:
        """Search Google Places for businesses matching a single category.

        Handles pagination automatically up to `max_pages_per_category` pages.
        Each page returns up to 20 results. A 2-second sleep is required between
        paginated requests because the `next_page_token` has a server-side
        propagation delay before it becomes valid.

        Args:
            category: A dict from TARGET_CATEGORIES with `name` and `query` keys.
            latitude, longitude: Center point of the search area.
            radius_miles: Search radius (converted to meters for the API).

        Returns:
            A flat list of raw Place objects from the API across all fetched pages.
        """
        results: list[dict[str, Any]] = []
        params = {
            "query": category["query"],
            "location": f"{latitude},{longitude}",
            "radius": miles_to_meters(radius_miles),
            "key": self.api_key,
        }

        for page_number in range(self.max_pages_per_category):
            response = requests.get(TEXT_SEARCH_URL, params=params, timeout=30)
            payload = self._parse_response(response, allow_zero_results=True)
            results.extend(payload.get("results", []))

            next_page_token = payload.get("next_page_token")
            if not next_page_token or page_number + 1 >= self.max_pages_per_category:
                break

            # Google requires a short delay before the next_page_token is usable.
            time.sleep(2)
            params = {"pagetoken": next_page_token, "key": self.api_key}

        return results

    def get_place_details(self, place_id: str) -> dict[str, Any]:
        """Fetch enriched details for a single place by its Place ID.

        The `fields` parameter limits which data is returned, which controls
        billing cost. Only fields actually used downstream are requested.

        Args:
            place_id: Google Places unique identifier for the business.

        Returns:
            A dict of place detail fields, or an empty dict if not found.
        """
        response = requests.get(
            DETAILS_URL,
            params={
                "place_id": place_id,
                "fields": (
                    "place_id,name,formatted_address,formatted_phone_number,"
                    "website,rating,user_ratings_total,url,business_status,reviews"
                ),
                "key": self.api_key,
            },
            timeout=30,
        )
        payload = self._parse_response(response)
        return payload.get("result", {})

    def get_place_reviews(self, place_id: str) -> list[dict]:
        """Fetch up to 5 five-star Google reviews for a single place.

        Calls get_place_details() which now includes the reviews field.
        Google Places API returns a maximum of 5 reviews sorted by
        relevance — the same reviews highlighted in the Google Maps UI.

        Only five-star reviews (rating == 5) are returned. This ensures
        the brand brief and cold call script are grounded in the strongest,
        most representative customer feedback.

        Args:
            place_id: Google Places unique identifier for the business.

        Returns:
            List of up to 5 five-star review dicts, each containing:
              - author_name: str
              - rating: int
              - text: str
              - relative_time_description: str
            Returns empty list if no five-star reviews are found.
            Preserves Google's relevance-ranked order.
        """
        details = self.get_place_details(place_id)
        all_reviews = details.get("reviews", [])

        # Filter to five-star reviews only — preserve Google's relevance order
        five_star = [r for r in all_reviews if r.get("rating") == 5]

        # Return only the fields needed downstream
        return [
            {
                "author_name": r.get("author_name", "Anonymous"),
                "rating": r.get("rating"),
                "text": r.get("text", "").strip(),
                "relative_time_description": r.get("relative_time_description", ""),
            }
            for r in five_star
        ]

    def discover_prospects(
        self,
        categories: list[dict[str, Any]],
        zip_code: str,
        radius_miles: float,
    ) -> list[dict[str, Any]]:
        """Search for business prospects across all target categories.

        Orchestrates the full discovery pipeline:
          1. Geocode the ZIP code to get a search center (lat/lng).
          2. For each category, run a Text Search within the radius.
          3. For each search result, fetch enriched Place Details.
          4. Skip non-operational businesses (permanently closed, etc.).
          5. Compute the distance from the search ZIP to each business.

        The business geometry (lat/lng) used for distance comes from the Text
        Search result rather than Place Details — geometry is not included in
        the Details fields we request, and the Text Search result is accurate
        enough for distance display purposes.

        Args:
            categories: List of category dicts from TARGET_CATEGORIES.
            zip_code: The user's input ZIP code (search origin).
            radius_miles: Search radius in miles.

        Returns:
            List of enriched prospect dicts ready for deduplication and scoring.
        """
        latitude, longitude = self.zip_to_location(zip_code)
        prospects: list[dict[str, Any]] = []

        for category in categories:
            search_results = self.search_category(category, latitude, longitude, radius_miles)
            for item in search_results:
                place_id = item.get("place_id")
                if not place_id:
                    continue

                details = self.get_place_details(place_id)

                # Skip businesses that are not currently operational (e.g., permanently closed).
                business_status = details.get("business_status") or item.get("business_status")
                if business_status and business_status != "OPERATIONAL":
                    continue

                # Business lat/lng comes from the Text Search geometry — Place Details
                # doesn't return geometry with our current field selection.
                biz_location = item.get("geometry", {}).get("location", {})
                biz_lat = biz_location.get("lat")
                biz_lng = biz_location.get("lng")
                if biz_lat is not None and biz_lng is not None:
                    distance_miles = haversine_distance(latitude, longitude, biz_lat, biz_lng)
                else:
                    distance_miles = ""

                prospects.append(
                    {
                        "place_id": place_id,
                        "business_name": details.get("name") or item.get("name", ""),
                        "category": category["name"],
                        "address": details.get("formatted_address") or item.get("formatted_address", ""),
                        "phone": details.get("formatted_phone_number", ""),
                        "website": details.get("website", ""),
                        "google_maps_url": details.get("url", ""),
                        "rating": details.get("rating") or item.get("rating", ""),
                        "review_count": (
                            details.get("user_ratings_total") or item.get("user_ratings_total", "")
                        ),
                        "distance_miles": distance_miles,
                        "source": "Google Places API",
                    }
                )

        return prospects

    @staticmethod
    def _parse_response(response: requests.Response, allow_zero_results: bool = False) -> dict[str, Any]:
        """Parse and validate a Google API JSON response.

        Google APIs return HTTP 200 even for application-level errors; the real
        status is in the JSON `status` field. This method surfaces those errors
        as Python exceptions so callers don't need to inspect raw payloads.

        Args:
            response: The raw requests.Response from a Google API call.
            allow_zero_results: If True, treat ZERO_RESULTS as non-fatal. Used
                for category searches where no matches in an area is expected.

        Raises:
            requests.HTTPError: on non-2xx HTTP status.
            RuntimeError: on application-level API errors (e.g., REQUEST_DENIED).
        """
        response.raise_for_status()
        payload = response.json()
        status = payload.get("status")
        allowed_statuses = {"OK"}
        if allow_zero_results:
            allowed_statuses.add("ZERO_RESULTS")

        if status not in allowed_statuses:
            message = payload.get("error_message", "No error message returned")
            raise RuntimeError(f"Google API error: {status}. {message}")

        return payload
