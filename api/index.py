"""Vercel entrypoint.

Vercel serves every file in ``api/`` as a serverless function. This file only
exposes the ASGI ``app``; all logic lives in the ``kriterion`` package so that
helper modules are never mistaken for functions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kriterion.main import app  # noqa: E402,F401
