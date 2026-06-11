from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from web.backend.app.config import ROOT
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.tool_console import ToolConsoleService


LOCAL_PATH_RE = __import__("re").compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_tool_console_lists_whitelisted_tools_only():
    payload = ToolConsoleService().list_tools()

    assert payload["summary"]["tool_count"] >= 20
    assert payload["safety"]["whitelist_only"] is True
    assert payload["safety"]["arbitrary_command_input"] is False
    assert payload["safety"]["qmt_write_enabled"] is False
    assert payload["safety"]["trading_enabled"] is False
    assert any(tool["id"] == "ingest_web_db" for tool in payload["tools"])
    assert any(tool["id"] == "generate_action_plan" for tool in payload["tools"])
    assert any(tool["id"] == "market_position_prompt" for tool in payload["tools"])
    RatioOnlyService.assert_safe(payload)


def test_tool_console_rejects_unknown_tool():
    with pytest.raises(KeyError):
        ToolConsoleService().run_tool("not-a-real-tool")


def test_tool_console_prompt_tool_does_not_execute_runner():
    calls: list[list[str]] = []

    def runner(args, **kwargs):  # noqa: ANN001, ANN003
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    result = ToolConsoleService(runner=runner).run_tool("strategy_briefing_prompt")

    assert result["status"] == "prompt"
    assert calls == []
    assert "docs/modules/STRATEGY_BRIEFING.md" in result["prompt"]
    RatioOnlyService.assert_safe(result)


def test_market_position_prompt_is_manual_and_mentions_complete_trade_day():
    result = ToolConsoleService().run_tool("market_position_prompt")

    assert result["status"] == "prompt"
    assert "docs/modules/MARKET_POSITION.md" in result["prompt"]
    assert "basis_trade_date" in result["prompt"]
    assert "最新完整交易日" in result["prompt"]
    RatioOnlyService.assert_safe(result)


def test_theme_research_prompt_covers_formal_refresh_workflow():
    result = ToolConsoleService().run_tool("theme_research_prompt")

    assert result["status"] == "prompt"
    prompt = result["prompt"]
    assert "docs/modules/THEME_RESEARCH.md" in prompt
    assert "templates/theme_review_template.md" in prompt
    assert "最新完整交易日" in prompt
    assert "theme_review_YYYY-MM-DD_HHMMSS" in prompt
    assert "research/themes/theme_registry.json" in prompt
    assert "scripts/generate_theme_leaders.py" in prompt
    assert "scripts/ingest_current_state.py" in prompt
    assert "scripts/web_check.py" in prompt
    RatioOnlyService.assert_safe(result)


def test_tool_console_run_sanitizes_output():
    calls: list[list[str]] = []
    unsafe_text = f"OK {ROOT} total_asset account 1000万元"

    def runner(args, **kwargs):  # noqa: ANN001, ANN003
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=unsafe_text, stderr="")

    result = ToolConsoleService(runner=runner).run_tool("project_check_current")

    assert result["status"] == "passed"
    assert calls
    stdout = result["steps"][0]["stdout"]
    assert "[repo]" in stdout
    assert str(ROOT) not in stdout
    assert "total_asset" not in stdout
    assert "account" not in stdout.lower()
    assert "万元" not in stdout
    RatioOnlyService.assert_safe(result)


def test_qmt_snapshot_rebuilds_target_allocation_before_refreshing_db():
    calls: list[list[str]] = []

    def runner(args, **kwargs):  # noqa: ANN001, ANN003
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")

    result = ToolConsoleService(runner=runner).run_tool("qmt_snapshot")

    assert result["status"] == "passed"
    assert [step["name"] for step in result["steps"]] == [
        "main",
        "rebuild_target_allocation",
        "refresh_latest_index",
        "refresh_web_db",
    ]
    assert calls[0][:3] == ["py", "-3.11", "scripts/qmt_portfolio_snapshot.py"]
    assert "scripts/generate_target_allocation.py" in calls[1]
    assert "--sync-intraday-rules" in calls[1]
    assert "scripts/build_latest_index.py" in calls[2]
    assert "scripts/ingest_current_state.py" in calls[3]
    RatioOnlyService.assert_safe(result)


def test_tools_page_and_ops_api_are_safe(client):
    response = client.get("/tools")
    assert response.status_code == 200
    html = response.text
    assert "data-tool-search" in html
    assert "data-tool-filter" in html
    assert "toolRows" in html
    assert "data-tool-output-row" in html
    assert "tool-result-row" in html
    assert not LOCAL_PATH_RE.search(html)

    response = client.get("/ops/tools")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    RatioOnlyService.assert_safe(payload)

    response = client.post("/ops/run/strategy_briefing_prompt")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "prompt"
    RatioOnlyService.assert_safe(payload)

    response = client.post("/ops/run/not-a-real-tool")
    assert response.status_code == 404
