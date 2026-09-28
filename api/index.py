"""Vercel serverless entrypoint.

Vercel expects a module-level `app` (ASGI) in `api/index.py`.
We import the FastAPI app and re-export it. We also patch the
clone directory to /tmp because Vercel's filesystem is read-only
outside /tmp.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Redirect clone temp dir to /tmp (writable on Vercel)
os.environ["JEV_CLONES_DIR"] = "/tmp/.jev_clones"

# Patch sources module BEFORE importing app so TMP_ROOT reflects env var.
from app.analyzer import sources as _sources
_sources.TMP_ROOT = Path(os.environ["JEV_CLONES_DIR"])
_sources.TMP_ROOT.mkdir(parents=True, exist_ok=True)

from app.server import app  # noqa: E402  (must come after sys.path/patches)
