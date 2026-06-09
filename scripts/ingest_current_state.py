#!/usr/bin/env python3
"""Compatibility entrypoint for ingesting current state into the Web SQLite DB."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ingest_current_state_to_web_db import main


if __name__ == "__main__":
    sys.exit(main())
