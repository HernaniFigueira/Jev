"""Vercel serverless entrypoint.

Vercel expects an ASGI `app` (or `handler`) at module level in `api/index.py`.
This module:
  1) Adds the project root to sys.path.
  2) Redirects temporary clones to /tmp (Vercel FS is read-only outside /tmp).
  3) Imports the FastAPI `app` and also exposes a `handler` alias for older
     @vercel/python runtimes that expect a WSGI handler (our `app` is ASGI).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Resolve the project root (parent of api/).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Also chdir so relative paths like STATIC_DIR resolve correctly on Vercel,
# because Vercel invokes the function from a different CWD.
os.chdir(str(ROOT))

# Redirect temp clones to /tmp
os.environ.setdefault("JEV_CLONES_DIR", "/tmp/.jev_clones")
from app.analyzer import sources as _sources  # noqa: E402
_sources.TMP_ROOT = Path(os.environ["JEV_CLONES_DIR"])
_sources.TMP_ROOT.mkdir(parents=True, exist_ok=True)

# Import the FastAPI app (ASGI). Vercel's Python runtime will serve `app`.
from app.server import app as app  # noqa: E402,F811  (re-export)

# For Vercel runtimes that look for `handler` (WSGI), we don't provide one since
# FastAPI is ASGI; exposing `app` is sufficient for recent @vercel/python.
