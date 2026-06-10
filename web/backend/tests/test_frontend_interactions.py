from __future__ import annotations


def test_pages_include_refresh_export_and_interaction_hooks(client):
    response = client.get("/portfolio")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "/api/export/review_package" in html
    assert "data-table-search=\"portfolioTable\"" in html
    assert "data-sort=\"number\"" in html


def test_environment_page_include_refresh_and_status_hooks(client):
    response = client.get("/settings")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "/api/environment/status" in html
    assert "data-environment-section=\"git\"" in html
    assert "data-environment-section=\"safety\"" in html
    assert "data-status-card=\"env-readonly\"" in html
    assert "data-bind=\"env_branch\"" in html
    assert "environmentCheckRows" in html
    script = client.get("/static/app.js").text
    assert "function renderEnvironment" in script
    assert "no_order_generation" in script


def test_subject_gap_page_include_refresh_and_table_hooks(client):
    response = client.get("/subjects/gap")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-gap-chart" in html
    assert "subjectGapChart" in html
    assert "subjectGapTooltip" in html
    assert "data-table-search=\"subjectGapTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "subjectGapRows" in html


def test_history_gap_page_include_refresh_filter_and_table_hooks(client):
    response = client.get("/history/gap-dashboard")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-history-gap-chart" in html
    assert "historyGapChart" in html
    assert "historyGapTooltip" in html
    assert "data-table-search=\"historyGapTable\"" in html
    assert "data-table-filter=\"historyGapTable\"" in html
    assert "data-table-search=\"historyEntryTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "historyGapRows" in html
    assert "historyEntryRows" in html


def test_subject_page_include_refresh_and_table_hooks(client):
    response = client.get("/subjects")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-table-search=\"subjectsTable\"" in html
    assert "data-sort=\"text\"" in html
    assert "subjectsRows" in html


def test_themes_page_include_refresh_filter_and_table_hooks(client):
    response = client.get("/themes")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-table-search=\"themesTable\"" in html
    assert "data-table-filter=\"themesTable\"" in html
    assert "data-filter-key=\"status\"" in html
    assert "data-filter-key=\"tactical_rating\"" in html
    assert "data-filter-key=\"stage\"" in html
    assert "data-sort=\"text\"" in html
    assert "themesRows" in html


def test_allocation_drilldown_pages_include_refresh_filter_and_table_hooks(client):
    response = client.get("/buckets/drilldown")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "bucketDrilldownChart" in html
    assert "bucketDrilldownTooltip" in html
    assert "data-table-search=\"bucketDrilldownTable\"" in html
    assert "data-table-filter=\"bucketDrilldownTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "bucketDrilldownRows" in html

    response = client.get("/subjects/drilldown")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-table-search=\"subjectDrilldownTable\"" in html
    assert "data-table-filter=\"subjectDrilldownTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "subjectDrilldownRows" in html


def test_buckets_page_include_refresh_filter_and_table_hooks(client):
    response = client.get("/buckets")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-table-search=\"bucketTable\"" in html
    assert "data-table-search=\"bucketSubjectTable\"" in html
    assert "data-table-filter=\"bucketTable\"" in html
    assert "data-table-filter=\"bucketSubjectTable\"" in html
    assert "data-filter-key=\"gap_status\"" in html
    assert "data-filter-key=\"bucket\"" in html
    assert "data-filter-key=\"gate_conclusion\"" in html
    assert "data-sort=\"number\"" in html
    assert "bucketRows" in html
    assert "bucketSubjectRows" in html


def test_decision_timeline_page_include_refresh_filter_and_table_hooks(client):
    response = client.get("/decision-timeline")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-decision-timeline-chart" in html
    assert "decisionTimelineChart" in html
    assert "decisionTimelineTooltip" in html
    assert "data-table-search=\"decisionTimelineTable\"" in html
    assert "data-table-filter=\"decisionTimelineTable\"" in html
    assert "data-sort=\"text\"" in html
    assert "decisionTimelineRows" in html


def test_historical_metrics_page_include_refresh_filter_and_table_hooks(client):
    response = client.get("/historical-metrics")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "data-historical-metrics-chart" in html
    assert "historicalMetricsChart" in html
    assert "historicalMetricsTooltip" in html
    assert "data-table-search=\"historicalMetricTable\"" in html
    assert "data-table-filter=\"historicalMetricTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "historicalMetricRows" in html


def test_dashboard_includes_gap_chart_and_status_cards(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "bucketGapChart" in html
    assert "/api/dashboard/current" in html
    assert "data-dashboard-section=\"system-status\"" in html
    assert "data-dashboard-section=\"market-position\"" in html
    assert "data-dashboard-section=\"action-plan-summary\"" in html
    assert "data-dashboard-section=\"allocation-summary\"" in html
    assert "data-dashboard-section=\"subject-summaries\"" in html
    assert "dashboardQuickLinks" in html
    assert "data-status-card=\"research-first\"" in html
    assert "data-status-card=\"intraday\"" in html


def test_frontend_script_has_refresh_sanitizer_pagination_and_expand_logic(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    script = response.text
    assert "function assertRatioOnly" in script
    assert "function renderPagination" in script
    assert "function renderSubjectGap" in script
    assert "function renderSubjectGapChart" in script
    assert "function renderDashboardQuickLinks" in script
    assert "function renderEnvironment" in script
    assert "function renderThemes" in script
    assert "function renderBucketDrilldown" in script
    assert "function renderBucketDrilldownChart" in script
    assert "function renderSubjectDrilldown" in script
    assert "function renderHistoryGapDashboard" in script
    assert "function renderHistoryGapChart" in script
    assert "function renderBuckets" in script
    assert "function renderDecisionTimeline" in script
    assert "function renderDecisionTimelineChart" in script
    assert "function renderHistoricalMetricsChart" in script
    assert "function updateHistoricalMetricsSummary" in script
    assert "function setupFilters" in script
    assert "mouseenter" in script
    assert "gapStatus" in script
    assert "function renderSubjectStatus" in script
    assert "detail-row" in script
    assert "setInterval(refresh" in script
