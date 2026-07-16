"""Backend compatibility package for shared prospecting modules.

WHAT: Import bridge for the FastAPI backend's historical `prospecting.*` imports.
DOES: Adds the repository root to sys.path so wrappers can import shared.prospecting.
USED_BY: service-prospecting-backend/main.py, service helpers, and backend tests.
REQUIRES: The backend to be run from inside the repository checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

