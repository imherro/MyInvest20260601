from __future__ import annotations

import re


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_web_pages_render_without_local_absolute_paths(client):
    paths = [
        "/",
        "/action-plan",
        "/target-allocation",
        "/research-first",
        "/subjects/gap",
        "/portfolio",
        "/intraday-rules",
        "/decision-log",
        "/system-checks",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert not LOCAL_PATH_RE.search(response.text)
