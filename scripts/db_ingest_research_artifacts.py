#!/usr/bin/env python3
"""Import research JSON artifacts into the MyInvest history database."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.ingest import cli_main  # noqa: E402


if __name__ == "__main__":
    sys.exit(cli_main())
