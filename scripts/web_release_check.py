from __future__ import annotations

import argparse

from web_check import WebCheck


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Run the MyInvest Web release check.")


def main() -> int:
    build_parser().parse_args()
    return WebCheck(mode="release").run()


if __name__ == "__main__":
    raise SystemExit(main())
