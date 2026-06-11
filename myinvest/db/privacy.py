"""Privacy scanning for DB artifact ingestion."""

from __future__ import annotations

import re
from typing import Any


FORBIDDEN_KEYS = {
    "account",
    "account_id",
    "acct",
    "full_account",
    "order_id",
    "order_no",
    "order_record",
    "order_records",
    "trade_id",
    "deal_id",
    "quantity",
    "volume_shares",
    "shares",
    "amount",
    "market_value",
    "cost_amount",
    "cost_value",
    "current_value_amount",
}
ALLOWED_PRICE_KEYS = {
    "price",
    "last_price",
    "close",
    "open",
    "high",
    "low",
    "current_price",
    "cost_price",
    "last_reference",
    "current_value",
}
FORBIDDEN_KEY_TERMS = (
    "持仓数量",
    "股数",
    "市值",
    "成交金额",
    "委托",
    "订单",
    "账号",
    "账户资产",
)
LOCAL_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:\\(?:Users|Documents|Program Files|Windows|国金证券|[^\\]+)\\")
TOKEN_TEXT_RE = re.compile(r"\b(?:token|password|secret|api[_-]?key)\b", re.IGNORECASE)


def normalized_key(key: Any) -> str:
    return str(key).strip().lower()


def is_forbidden_key(key: Any) -> bool:
    text = normalized_key(key)
    if text in ALLOWED_PRICE_KEYS:
        return False
    if text.endswith("_policy") or text in {"privacy_policy", "amount_policy"}:
        return False
    if text in FORBIDDEN_KEYS:
        return True
    if "share_count" in text:
        return True
    tokens = {token for token in re.split(r"[^a-z0-9]+", text) if token}
    if tokens & {"amount", "quantity", "shares", "account"}:
        return True
    if "fill" in tokens and ("record" in tokens or "records" in tokens):
        return True
    if "order" in tokens and ("record" in tokens or "records" in tokens):
        return True
    return any(term in str(key) for term in FORBIDDEN_KEY_TERMS)


def scan_json_privacy(data: Any) -> list[dict[str, str]]:
    """Return privacy findings for fields that must not be stored in raw JSON."""

    findings: list[dict[str, str]] = []

    def walk(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = (*path, str(key))
                if is_forbidden_key(key):
                    findings.append(
                        {
                            "path": ".".join(child_path),
                            "reason": "forbidden_key",
                            "term": str(key),
                        }
                    )
                    continue
                walk(child, child_path)
            return

        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, (*path, str(index)))
            return

        if isinstance(value, str):
            if LOCAL_ABSOLUTE_PATH_RE.search(value):
                findings.append(
                    {
                        "path": ".".join(path),
                        "reason": "local_absolute_path",
                        "term": "absolute_path",
                    }
                )
            if TOKEN_TEXT_RE.search(value) and ("=" in value or ":" in value):
                findings.append(
                    {
                        "path": ".".join(path),
                        "reason": "credential_like_text",
                        "term": "credential",
                    }
                )

    walk(data, ())
    return findings
