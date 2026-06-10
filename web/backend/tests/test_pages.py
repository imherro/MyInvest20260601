from __future__ import annotations

import re


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_web_pages_render_without_local_absolute_paths(client):
    paths = [
        "/",
        "/dashboard",
        "/action-plan",
        "/target-allocation",
        "/research-first",
        "/subjects",
        "/subjects/gap",
        "/themes",
        "/history/gap-dashboard",
        "/buckets",
        "/portfolio",
        "/intraday-rules",
        "/decision-log",
        "/system-checks",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert not LOCAL_PATH_RE.search(response.text)


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
