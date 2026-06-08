#!/usr/bin/env python3
"""Build research/latest_index.json from business timestamps and hashes."""

from __future__ import annotations

import json
import sys

from project_utils import LATEST_INDEX, build_latest_index, rel_path, write_json


def main() -> int:
    index = build_latest_index()
    write_json(LATEST_INDEX, index)
    print(
        json.dumps(
            {
                "created": rel_path(LATEST_INDEX),
                "modules": sorted(index.get("modules", {}).keys()),
                "files": len(index.get("files", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

