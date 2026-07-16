"""Shared prospect discovery primitives.

WHAT: Source-of-truth package for scraper, scoring, category, and dedupe logic.
DOES: Keeps Google Places discovery and prospect preparation logic in one place.
USED_BY: CLI wrappers at the project root and FastAPI wrappers in the backend.
REQUIRES: Component-specific config modules to provide environment values.
"""

