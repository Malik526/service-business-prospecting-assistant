"""Google Places and Geocoding API client."""

from __future__ import annotations

import time
from typing import Any

import requests

from utils import miles_to_meters


GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


class GooglePlacesClient:
    def __init__(self, api_key: str, max_pages_per_category: int = 3) -> None:
        self.api_key = api_key
        self.max_pages_per_category = max_pages_per_category

    def zip_to_location(self, zip_code: str) -> tuple[float, float]:
        response = requests.get(
            GEOCODE_URL,
            params={
                "address": zip_code,
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

            time.sleep(2)
            params = {"pagetoken": next_page_token, "key": self.api_key}

        return results

    def get_place_details(self, place_id: str) -> dict[str, Any]:
        response = requests.get(
            DETAILS_URL,
            params={
                "place_id": place_id,
                "fields": (
                    "place_id,name,formatted_address,formatted_phone_number,"
                    "website,rating,user_ratings_total,url,business_status"
                ),
                "key": self.api_key,
            },
            timeout=30,
        )
        payload = self._parse_response(response)
        return payload.get("result", {})

    def discover_prospects(
        self,
        categories: list[dict[str, Any]],
        zip_code: str,
        radius_miles: float,
    ) -> list[dict[str, Any]]:
        latitude, longitude = self.zip_to_location(zip_code)
        prospects: list[dict[str, Any]] = []

        for category in categories:
            search_results = self.search_category(category, latitude, longitude, radius_miles)
            for item in search_results:
                place_id = item.get("place_id")
                if not place_id:
                    continue

                details = self.get_place_details(place_id)
                business_status = details.get("business_status") or item.get("business_status")
                if business_status and business_status != "OPERATIONAL":
                    continue

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
                        "review_count": details.get("user_ratings_total")
                        or item.get("user_ratings_total", ""),
                        "source": "Google Places API",
                    }
                )

        return prospects

    @staticmethod
    def _parse_response(response: requests.Response, allow_zero_results: bool = False) -> dict[str, Any]:
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
