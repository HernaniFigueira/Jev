"""Vercel serverless entrypoint.

Vercel expects an ASGI/WSGI handler in `api/index.py`. We import the FastAPI
app from app.server and re-export it as `app`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Redirect temporary clones to /tmp (Vercel filesystem is read-only outside /tmp)
os.environ.setdefault("JEV_CLONES_DIR", "/tmp/.jev_clones")
from app.analyzer import sources as _sources
_sources.TMP_ROOT = Path(os.environ["JEV_CLONES_DIR"])
_sources.TMP_ROOT.mkdir(parents=True, exist_ok=True)

from app.server import app  # noqa: E402

# Vercel Python runtime needs an `app` (ASGI) or `handler` (WSGI) object.
# FastAPI is ASGI natively.
