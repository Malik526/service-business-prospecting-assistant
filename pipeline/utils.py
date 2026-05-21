"""Shared utility functions for the research pipeline.

Provides:
  - slugify: Convert a business name string to a URL/filename-safe slug.
  - setup_logger: Return a consistently-formatted logger for any module in the pipeline.
"""

from __future__ import annotations

import logging
import re


def slugify(name: str) -> str:
    """Convert a business name to a lowercase, hyphen-separated filename slug.

    Steps:
      1. Lowercase the string.
      2. Remove all characters that are not letters, digits, spaces, or hyphens.
      3. Replace runs of whitespace or underscores with a single hyphen.
      4. Collapse consecutive hyphens into one.
      5. Strip leading/trailing hyphens.

    Example: "Glow Aesthetics & Med Spa NYC" → "glow-aesthetics-med-spa-nyc"

    Args:
        name: The business name string to slugify.

    Returns:
        A URL-safe, lowercase, hyphen-separated slug string.
    """
    name = name.lower()
    # Remove characters that are not word chars, spaces, or hyphens
    name = re.sub(r"[^\w\s-]", "", name)
    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)
    # Collapse multiple consecutive hyphens
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def setup_logger(name: str) -> logging.Logger:
    """Return a named logger with a consistent [TIMESTAMP] LEVEL - name - message format.

    Attaches a StreamHandler if none already exist on the logger, preventing
    duplicate log lines when the module is imported multiple times.

    Args:
        name: Logger name, typically the module or component name (e.g. "pipeline.research").

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on re-import
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
