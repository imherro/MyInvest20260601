from __future__ import annotations


def test_required_api_endpoints(client):
    paths = [
        "/api/health",
        "/api/dashboard/current",
        "/api/current",
        "/api/latest-index",
        "/api/modules/current",
        "/api/subjects/status",
        "/api/subjects/status/511360.SH",
        "/api/subjects/freshness",
        "/api/subjects/gap",
        "/api/themes/status",
        "/api/buckets/status",
        "/api/buckets/drilldown?detail=full",
        "/api/subjects/drilldown?detail=full",
        "/api/subjects/drilldown?subject=511360.SH&detail=full",
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
        "/api/history/gap-summary",
        "/api/portfolio/current",
        "/api/intraday-rules/current",
        "/api/research-first/current",
        "/api/system-check/current",
        "/api/decision-log/current",
        "/api/decision-timeline",
        "/api/decision-timeline/current-action-plan",
        "/api/historical-metrics",
        "/api/historical-metrics/bucket-attack_mainline",
        "/api/export/review_package?format=json",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        payload = response.json()
        assert payload["ok"] is True


def test_action_plan_api_enriches_market_state_from_current_market_score(client):
    response = client.get("/api/action-plan/current")
    assert response.status_code == 200
    plan = response.json()["data"]["action_plan"]
    assert plan["market_state"]
    assert plan["market_score"] is not None
    assert plan["market_basis_trade_date"]
