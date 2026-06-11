from __future__ import annotations

import re


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_readiness_page_renders_safe_summary_and_hooks(client):
    response = client.get("/readiness")

    assert response.status_code == 200
    html = response.text
    assert "Workbench Readiness" in html
    assert "/api/readiness/summary" in html
    assert "/api/readiness/checks" in html
    assert "data-readiness-section=\"summary\"" in html
    assert "data-readiness-section=\"controls\"" in html
    assert "data-readiness-section=\"signals\"" in html
    assert "data-readiness-section=\"safety\"" in html
    assert "data-readiness-view=\"summary\"" in html
    assert "data-readiness-view=\"checks\"" in html
    assert "readinessCheckRows" in html
    assert "readinessSafetyRows" in html
    assert "readinessReasonRows" in html
    assert "/static/readiness.js" in html
    assert "data-refresh" in html
    assert not LOCAL_PATH_RE.search(html)


def test_readiness_static_script_refreshes_only_get_endpoints(client):
    response = client.get("/static/readiness.js")

    assert response.status_code == 200
    script = response.text
    assert "function refreshReadiness" in script
    assert "function renderReadiness" in script
    assert "function assertSafe" in script
    assert "/api/readiness/summary" in script
    assert "/api/readiness/checks" in script
    assert "fetch(url" in script
    assert "POST" not in script
    assert "PUT" not in script
    assert "PATCH" not in script
    assert "DELETE" not in script


def test_readiness_page_openapi_stays_get_only(client):
    schema = client.get("/openapi.json").json()

    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/"):
            assert not (set(methods) & {"post", "put", "patch", "delete"}), path
