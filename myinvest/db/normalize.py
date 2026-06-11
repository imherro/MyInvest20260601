"""Normalization helpers for DB-first research history."""

from __future__ import annotations

import re
from typing import Any


CODE_WITH_EXCHANGE_RE = re.compile(r"(?P<code>\d{6})[._-](?P<exchange>SH|SZ)(?![A-Z0-9])", re.IGNORECASE)
EXCHANGE_PREFIX_RE = re.compile(r"(?P<exchange>SH|SZ)[._-](?P<code>\d{6})(?!\d)", re.IGNORECASE)
CODE_ONLY_RE = re.compile(r"\b(?P<code>\d{6})\b")
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
PP_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*(?:pp|percentage points?|percentage point|个百分点)", re.IGNORECASE)


def normalize_security_code(raw: str | None, name: str | None = None) -> dict[str, Any]:
    """Return normalized code fields without inventing an exchange.

    Examples:
    - ``688333.SH`` -> ``ts_code=688333.SH``, ``code_short=688333``, ``exchange=SH``
    - ``688333_SH`` -> ``ts_code=688333.SH``, ``code_short=688333``, ``exchange=SH``
    - ``valuation_688333_SH_name_2026-06-09_153822.json`` -> ``688333.SH``
    - ``511360`` -> ``ts_code=None``, ``code_short=511360``, ``exchange=None``
    """

    text = str(raw or "").strip().upper()
    alias_candidates: list[str] = []
    if raw:
        alias_candidates.append(str(raw).strip())
    if name:
        alias_candidates.append(str(name).strip())

    match = CODE_WITH_EXCHANGE_RE.search(text) or EXCHANGE_PREFIX_RE.search(text)
    if match:
        code_short = match.group("code")
        exchange = match.group("exchange").upper()
        ts_code = f"{code_short}.{exchange}"
        alias_candidates.extend([code_short, ts_code, f"{code_short}_{exchange}"])
        return {
            "ts_code": ts_code,
            "code_short": code_short,
            "exchange": exchange,
            "alias_candidates": sorted({item for item in alias_candidates if item}),
        }

    match = CODE_ONLY_RE.search(text)
    if match:
        code_short = match.group("code")
        alias_candidates.append(code_short)
        return {
            "ts_code": None,
            "code_short": code_short,
            "exchange": None,
            "alias_candidates": sorted({item for item in alias_candidates if item}),
        }

    return {
        "ts_code": None,
        "code_short": None,
        "exchange": None,
        "alias_candidates": sorted({item for item in alias_candidates if item}),
    }


def parse_pct_range(text: str | None) -> tuple[float | None, float | None]:
    """Parse a percentage range such as ``30%-40%`` into numeric endpoints."""

    if text is None:
        return None, None
    values = [abs(float(item)) for item in NUMBER_RE.findall(str(text))]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return values[0], values[1]


def parse_suggested_change_pp(text: str | None) -> tuple[float | None, float | None]:
    """Parse suggested percentage-point changes while preserving raw text elsewhere.

    Examples:
    - ``reduce 3.5pp to 8.5pp`` -> ``(3.5, 8.5)``
    - ``increase 5pp`` -> ``(5.0, 5.0)``
    """

    if text is None:
        return None, None
    raw = str(text)
    values = [abs(float(item)) for item in PP_RE.findall(raw)]
    if not values and ("pp" in raw.lower() or "percentage point" in raw.lower() or "百分点" in raw):
        values = [abs(float(item)) for item in NUMBER_RE.findall(raw)]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return values[0], values[1]
