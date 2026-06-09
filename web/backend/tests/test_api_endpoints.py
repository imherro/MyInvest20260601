from __future__ import annotations


def test_required_api_endpoints(client):
    paths = [
        "/api/health",
        "/api/current",
        "/api/latest-index",
        "/api/modules/current",
        "/api/action-plan/current",
        "/api/target-allocation/current",
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
