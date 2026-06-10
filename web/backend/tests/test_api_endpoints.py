from __future__ import annotations


def test_required_api_endpoints(client):
    paths = [
        "/api/health",
        "/api/current",
        "/api/latest-index",
        "/api/modules/current",
        "/api/subjects/status",
        "/api/subjects/status/511360.SH",
        "/api/subjects/freshness",
        "/api/subjects/gap",
        "/api/market-position/mapping",
        "/api/market-position/current",
        "/api/market-position/score/25",
        "/api/action-plan/current",
        "/api/target-allocation/current",
        "/api/target-allocation/shadow",
        "/api/target-allocation/shadow/compare",
        "/api/target-allocation/shadow/export?format=json",
        "/api/target-allocation/candidate-audit",
        "/api/target-allocation/candidate-audit?format=json",
        "/api/history/export",
        "/api/history/export?format=json",
        "/api/portfolio/current",
        "/api/intraday-rules/current",
        "/api/research-first/current",
        "/api/system-check/current",
        "/api/decision-log/current",
        "/api/export/review_package?format=json",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        payload = response.json()
        assert payload["ok"] is True
