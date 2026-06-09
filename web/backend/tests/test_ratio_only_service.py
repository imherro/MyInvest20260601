from __future__ import annotations

import pytest

from web.backend.app.services.ratio_only import RatioOnlyService, RatioOnlyViolation


def test_ratio_only_service_blocks_forbidden_key():
    with pytest.raises(RatioOnlyViolation):
        RatioOnlyService.assert_safe({"market_value": 1})


def test_ratio_only_service_sanitizes_text():
    data = RatioOnlyService.sanitize({"note": "C:/Users/example"})
    assert data["note"] == "[redacted_path]"
    RatioOnlyService.assert_safe(data)
