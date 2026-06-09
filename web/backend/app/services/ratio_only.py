from __future__ import annotations

import json
import re
from typing import Any


class RatioOnlyViolation(ValueError):
    pass


class RatioOnlyService:
    forbidden_key_re = re.compile(
        r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
        r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal|"
        r"cost_price|raw_cost_price|current_price|qmt_timetag)($|_)",
        re.IGNORECASE,
    )
    local_path_re = re.compile(r"(?:[A-Za-z]:(?!//)[\\/][^\s,;)]*|\\\\[^\s,;)]*|/Users/[^\s,;)]*|/home/[^\s,;)]*)")
    forbidden_text_re = re.compile(
        r"(总资产|金额|市值|股数|数量|可用数量|交易金额|盈亏金额|账号|完整账号|订单|委托|成交|"
        r"total asset|market value|profit amount|trade amount|share count|available quantity|full account|"
        r"order id|fill record|deal record)",
        re.IGNORECASE,
    )
    amount_like_re = re.compile(r"[-+]?\d+(?:\.\d+)?\s*(?:元|万元|亿元|股|份|手)")

    @classmethod
    def sanitize_text(cls, value: str) -> str:
        text = cls.local_path_re.sub("[redacted_path]", value)
        text = cls.amount_like_re.sub("[redacted_value]", text)
        text = cls.forbidden_text_re.sub("[redacted_term]", text)
        return text

    @classmethod
    def sanitize(cls, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if cls.forbidden_key_re.search(key_text):
                    continue
                result[key_text] = cls.sanitize(item)
            return result
        if isinstance(value, list):
            return [cls.sanitize(item) for item in value]
        if isinstance(value, str):
            return cls.sanitize_text(value)
        return value

    @classmethod
    def assert_safe(cls, value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                key_path = f"{path}.{key_text}"
                if cls.forbidden_key_re.search(key_text):
                    raise RatioOnlyViolation(f"forbidden key {key_path}")
                cls.assert_safe(item, key_path)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                cls.assert_safe(item, f"{path}[{idx}]")
        elif isinstance(value, str):
            if cls.local_path_re.search(value):
                raise RatioOnlyViolation(f"local absolute path at {path}")
            if cls.amount_like_re.search(value) or cls.forbidden_text_re.search(value):
                raise RatioOnlyViolation(f"forbidden text at {path}")

    @classmethod
    def safe_json(cls, value: Any) -> str:
        sanitized = cls.sanitize(value)
        cls.assert_safe(sanitized)
        return json.dumps(sanitized, ensure_ascii=False, sort_keys=True)


ratio_only_service = RatioOnlyService()
