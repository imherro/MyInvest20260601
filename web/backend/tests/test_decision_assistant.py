from __future__ import annotations

import re

from web.backend.app.services.decision_assistant import DecisionAssistantService
from web.backend.app.services.ratio_only import RatioOnlyService


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_decision_assistant_service_payload_is_safe(client, web_db):
    from web.backend.app.db import SessionLocal

    with SessionLocal() as session:
        payload = DecisionAssistantService(session).daily()

    RatioOnlyService.assert_safe(payload)
    assert payload["module"] == "decision_assistant_daily"
    assert payload["current_only"] is True
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["trading_feature"] is False
    assert payload["today"]["market_score"] is not None
    assert len(payload["risk_heatmap"]["items"]) >= 6
    assert len(payload["next_steps"]) >= 4
    assert "research_priorities" in payload
    assert "scenario_simulation" in payload
    assert "allocation_drift" in payload
    assert "review_loop" in payload
    assert "history_visuals" in payload
    assert "explanations" in payload


def test_decision_assistant_suite_service_payloads_are_safe(client, web_db):
    from web.backend.app.db import SessionLocal

    with SessionLocal() as session:
        service = DecisionAssistantService(session)
        payloads = [
            service.risk_center(),
            service.research_tasks(),
            service.preference_simulation(),
            service.deep_scenarios(),
            service.history_visuals_page(),
            service.review_score(),
            service.premarket_workflow(),
            service.global_search("688333"),
            service.security_center("688333.SH"),
            service.weekly_safety(),
        ]

    for payload in payloads:
        RatioOnlyService.assert_safe(payload)
        assert payload["current_only"] is True
        assert payload["safety"]["read_only"] is True
        assert payload["safety"]["trading_feature"] is False

    assert payloads[0]["module"] == "assistant_risk_center"
    assert payloads[1]["summary"]["task_count"] >= 0
    assert payloads[2]["summary"]["mode_count"] == 3
    assert payloads[3]["summary"]["scenario_count"] >= 1
    assert payloads[4]["summary"]["visual_count"] >= 4
    assert payloads[5]["summary"]["overall_score"] >= 0
    assert payloads[6]["summary"]["step_count"] >= 7
    assert payloads[7]["summary"]["result_count"] >= 0
    assert payloads[8]["code"] == "688333.SH"
    assert payloads[9]["summary"]["history_visual_count"] >= 4


def test_decision_assistant_api(client):
    response = client.get("/api/assistant/daily")
    assert response.status_code == 200
    payload = response.json()
    RatioOnlyService.assert_safe(payload)
    assert payload["ok"] is True
    data = payload["data"]
    assert data["today"]["system_status"]
    assert data["risk_heatmap"]["summary"]["item_count"] == len(data["risk_heatmap"]["items"])
    assert data["scenario_simulation"]["summary"]["scenario_count"] == len(data["scenario_simulation"]["items"])
    assert all("href" in item for item in data["next_steps"])


def test_decision_assistant_suite_apis(client):
    paths = [
        "/api/assistant/risk-center",
        "/api/assistant/research-tasks",
        "/api/assistant/preferences",
        "/api/assistant/scenarios",
        "/api/assistant/history-visuals",
        "/api/assistant/review-score",
        "/api/assistant/premarket",
        "/api/assistant/search?q=688333",
        "/api/assistant/securities/688333.SH",
        "/api/assistant/weekly-safety",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        payload = response.json()
        RatioOnlyService.assert_safe(payload)
        assert payload["ok"] is True
        assert payload["data"]["current_only"] is True


def test_decision_assistant_page(client):
    response = client.get("/assistant")
    assert response.status_code == 200
    html = response.text
    assert "每日指挥台" in html
    assert "/api/assistant/daily" in html
    for marker in [
        'data-assistant-section="today"',
        'data-assistant-section="next-steps"',
        'data-assistant-section="risk-heatmap"',
        'data-assistant-section="research-priorities"',
        'data-assistant-section="scenario-simulation"',
        'data-assistant-section="allocation-drift"',
        'data-assistant-section="review-loop"',
        'data-assistant-section="history-visuals"',
        'data-assistant-section="explanations"',
    ]:
        assert marker in html
    assert not LOCAL_PATH_RE.search(html)


def test_decision_assistant_suite_pages(client):
    cases = [
        ("/assistant/risk-center", "风险预警中心"),
        ("/assistant/research-tasks", "研究任务闭环"),
        ("/assistant/preferences", "偏好模拟"),
        ("/assistant/scenarios", "深度情景推演"),
        ("/assistant/history-visuals", "历史可视化"),
        ("/assistant/review-score", "复盘评分"),
        ("/assistant/premarket", "一键盘前流程"),
        ("/assistant/search?q=688333", "全局搜索"),
        ("/assistant/securities/688333.SH", "标的详情中心 688333.SH"),
        ("/assistant/weekly-safety", "安全周报"),
    ]
    for path, title in cases:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.text
        assert title in html
        assert "data-assistant-suite" in html
        assert "data-assistant-suite-table" in html
        assert not LOCAL_PATH_RE.search(html)
