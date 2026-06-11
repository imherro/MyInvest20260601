from __future__ import annotations

import re


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_web_pages_render_without_local_absolute_paths(client):
    paths = [
        "/",
        "/dashboard",
        "/settings",
        "/environment",
        "/preferences",
        "/audit",
        "/readiness",
        "/manager",
        "/researcher",
        "/trader",
        "/system",
        "/action-plan",
        "/target-allocation",
        "/research-first",
        "/subjects",
        "/subjects/gap",
        "/themes",
        "/history/gap-dashboard",
        "/buckets",
        "/buckets/drilldown",
        "/subjects/drilldown",
        "/portfolio",
        "/intraday-rules",
        "/decision-log",
        "/decision-timeline",
        "/historical-metrics",
        "/system-checks",
        "/tools",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert not LOCAL_PATH_RE.search(response.text)


def test_main_navigation_is_role_grouped(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert html.count('class="nav-trigger"') == 5
    for label in ["总览", "基金经理", "研究员", "操盘手", "历史库", "系统"]:
        assert label in html
    for href in [
        "/manager",
        "/researcher",
        "/trader",
        "/system",
        "/action-plan",
        "/target-allocation",
        "/subjects",
        "/portfolio",
        "/history/coverage",
        "/tools?group=基金经理",
        "/tools?group=研究员",
        "/tools?group=操盘手",
        "/tools?group=历史库与审计",
        "/tools?group=系统与开发",
    ]:
        assert href in html
    assert not LOCAL_PATH_RE.search(html)


def test_role_workbench_pages_are_grouped_and_safe(client):
    cases = [
        ("/manager", "manager", "基金经理工作台", "/tools?group=基金经理"),
        ("/researcher", "researcher", "研究员工作台", "/tools?group=研究员"),
        ("/trader", "trader", "操盘手工作台", "/tools?group=操盘手"),
        ("/system", "system", "系统与开发工作台", "/tools?group=系统与开发"),
    ]
    for path, role, title, tool_href in cases:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.text
        assert f'data-role-workbench="{role}"' in html
        assert title in html
        assert 'data-role-workflows' in html
        assert 'data-workflow-card' in html
        assert 'data-role-links' in html
        assert 'data-role-tools' in html
        assert tool_href in html
        assert "ratio-only" in html or "ResearchFirst" in html or "temp-only" in html
        assert not LOCAL_PATH_RE.search(html)


def test_tools_filter_highlights_owning_role(client):
    cases = [
        ("/tools?group=基金经理", "/manager", "基金经理"),
        ("/tools?group=研究员", "/researcher", "研究员"),
        ("/tools?group=操盘手", "/trader", "操盘手"),
        ("/tools?group=历史库与审计", "/history", "历史库"),
        ("/tools?group=系统与开发", "/system", "系统"),
    ]
    for path, href, label in cases:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.text
        pattern = rf'<div class="nav-group active">\s*<a class="nav-trigger" href="{re.escape(href)}">{label}</a>'
        assert re.search(pattern, html), path
        assert not LOCAL_PATH_RE.search(html)


def test_action_plan_page_distinguishes_plan_and_market_basis(client):
    response = client.get("/action-plan")
    assert response.status_code == 200
    html = response.text
    assert "Plan Basis" in html
    assert "Market Basis" in html
    assert 'data-bind="plan_market_score"' in html
    assert "n/a" not in re.sub(r"<table.*?</table>", "", html, flags=re.S)


def test_subject_gap_page_has_visual_and_refresh_hooks(client):
    response = client.get("/subjects/gap")
    assert response.status_code == 200
    html = response.text
    assert "subject-gap-chart-row" in html
    assert "data-gap-chart" in html
    assert "role=\"tooltip\"" in html
    assert "data-refresh" in html
    assert "data-table-search=\"subjectGapTable\"" in html
    assert "@media (max-width: 720px)" in html
    assert not LOCAL_PATH_RE.search(html)


def test_allocation_drilldown_pages_have_visual_and_table_hooks(client):
    response = client.get("/buckets/drilldown")
    assert response.status_code == 200
    html = response.text
    assert "bucketDrilldownChart" in html
    assert "data-drilldown-chart" in html
    assert "role=\"tooltip\"" in html
    assert "data-refresh" in html
    assert "data-table-search=\"bucketDrilldownTable\"" in html
    assert "data-table-filter=\"bucketDrilldownTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "bucketDrilldownRows" in html
    assert not LOCAL_PATH_RE.search(html)

    response = client.get("/subjects/drilldown")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-table-search=\"subjectDrilldownTable\"" in html
    assert "data-table-filter=\"subjectDrilldownTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "subjectDrilldownRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_history_gap_page_has_visual_and_refresh_hooks(client):
    response = client.get("/history/gap-dashboard")
    assert response.status_code == 200
    html = response.text
    assert "history-gap-chart-row" in html
    assert "data-history-gap-chart" in html
    assert "role=\"tooltip\"" in html
    assert "data-refresh" in html
    assert "data-table-search=\"historyGapTable\"" in html
    assert "data-table-filter=\"historyGapTable\"" in html
    assert "@media (max-width: 720px)" in html
    assert not LOCAL_PATH_RE.search(html)


def test_decision_timeline_page_has_visual_and_refresh_hooks(client):
    response = client.get("/decision-timeline")
    assert response.status_code == 200
    html = response.text
    assert "timeline-chart-row" in html
    assert "data-decision-timeline-chart" in html
    assert "role=\"tooltip\"" in html
    assert "data-refresh" in html
    assert "data-table-search=\"decisionTimelineTable\"" in html
    assert "data-table-filter=\"decisionTimelineTable\"" in html
    assert "@media (max-width: 720px)" in html
    assert not LOCAL_PATH_RE.search(html)


def test_historical_metrics_page_has_visual_and_refresh_hooks(client):
    response = client.get("/historical-metrics")
    assert response.status_code == 200
    html = response.text
    assert "historical-chart-row" in html
    assert "data-historical-metrics-chart" in html
    assert "role=\"tooltip\"" in html
    assert "data-refresh" in html
    assert "data-table-search=\"historicalMetricTable\"" in html
    assert "data-table-filter=\"historicalMetricTable\"" in html
    assert "@media (max-width: 720px)" in html
    assert not LOCAL_PATH_RE.search(html)
