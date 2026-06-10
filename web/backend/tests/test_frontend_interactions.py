from __future__ import annotations


def test_pages_include_refresh_export_and_interaction_hooks(client):
    response = client.get("/portfolio")
    assert response.status_code == 200
    html = response.text
    assert "data-refresh" in html
    assert "/api/export/review_package" in html
    assert "data-table-search=\"portfolioTable\"" in html
    assert "data-sort=\"number\"" in html

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
    assert "function renderThemes" in script
    assert "function renderBucketDrilldown" in script
    assert "function renderBucketDrilldownChart" in script
    assert "function renderSubjectDrilldown" in script
    assert "function setupFilters" in script
    assert "mouseenter" in script
    assert "gapStatus" in script
    assert "function renderSubjectStatus" in script
    assert "detail-row" in script
    assert "setInterval(refresh" in script
