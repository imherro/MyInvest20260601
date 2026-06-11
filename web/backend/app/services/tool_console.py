from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from ..config import ROOT
from .ratio_only import RatioOnlyService


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    title: str
    category: str
    kind: str
    impact: str
    description: str
    display_command: str = ""
    args: tuple[str, ...] = ()
    timeout_seconds: int = 180
    requires_qmt: bool = False
    refresh_web_db_after: bool = False
    post_success_steps: tuple[tuple[str, tuple[str, ...], int], ...] = ()
    prompt: str = ""
    href: str = ""

    def payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "kind": self.kind,
            "impact": self.impact,
            "description": self.description,
            "command_display": self.display_command,
            "requires_qmt": self.requires_qmt,
            "refreshes_web_db": self.refresh_web_db_after,
            "prompt": self.prompt,
            "href": self.href,
        }


def _py(*args: str) -> tuple[str, ...]:
    return (sys.executable, *args)


def _qmt_py(*args: str) -> tuple[str, ...]:
    return ("py", "-3.11", *args)


TOOL_GROUP_ORDER = (
    "日常使用",
    "组合与研究维护",
    "QMT 只读",
    "导出与审计",
    "开发验收",
    "Codex 研究提示",
)


TOOL_LAYOUT: dict[str, tuple[str, int, str]] = {
    "qmt_snapshot": ("日常使用", 10, "盘前或持仓变化后使用；先用 QMT 只读刷新组合比例快照。"),
    "ingest_web_db": ("日常使用", 20, "每天打开 Web 前、或生成任何新研究文件后使用；让页面读取最新 current state。"),
    "valuation_update_check": ("日常使用", 30, "盘前、盘中或复盘前使用；检查估值缺失、过期或跨区，只作为数据质量提示。"),
    "generate_premarket_check": ("日常使用", 40, "盘前已有操作建议后使用；生成当天执行检查和盘中监控清单。"),
    "intraday_once": ("日常使用", 50, "盘中使用；QMT 在线时按已固化规则做一次触发检查。"),
    "intraday_offline_once": ("日常使用", 55, "盘中或演示时使用；QMT 不在线时用参考价检查规则是否可读。"),
    "generate_post_market_review": ("日常使用", 70, "收盘后使用；对比盘前计划、盘中提醒和实际执行做日常复盘。"),
    "generate_weekly_review": ("日常使用", 80, "周末或周度复盘时使用；生成周度复盘草案。"),
    "generate_action_plan": ("组合与研究维护", 10, "市场仓位、组合快照、估值和 ResearchFirst 前置研究更新后使用。"),
    "generate_target_allocation": ("组合与研究维护", 20, "市场仓位或组合结构变化后使用；生成目标仓位并同步盘中规则。"),
    "build_latest_index": ("组合与研究维护", 30, "发现 latest_index 缺失、过期或刚批量生成研究文件后使用。"),
    "staleness_check": ("组合与研究维护", 40, "怀疑当前研究依赖已过期时使用；可同步 staleness 到盘中规则。"),
    "audit_holdings_research": ("组合与研究维护", 50, "持仓变化或补研究前使用；找出 profile、valuation、liquidity 缺口。"),
    "filter_current_backlog": ("组合与研究维护", 60, "已有 backlog 但只想看当前真实持仓相关任务时使用。"),
    "p2_position_review": ("组合与研究维护", 70, "大持仓需要单独复核时使用；输出比例口径复核。"),
    "theme_leaders": ("组合与研究维护", 80, "主线研究更新后使用；生成 ETF/个股候选池和 ResearchFirst 清单。"),
    "valuation_reports": ("组合与研究维护", 90, "补估值报告或盘中规则参考区间时使用；批量运行可能较慢。"),
    "repair_portfolio_snapshot": ("组合与研究维护", 100, "最近组合快照字段质量异常时使用；修复后再刷新 Web DB。"),
    "qmt_probe": ("QMT 只读", 10, "QMT 客户端刚打开后先使用；确认只读连接正常。"),
    "review_package": ("导出与审计", 10, "要发给外部模型或人工审阅前使用；生成 current-only 安全包。"),
    "export_shadow": ("导出与审计", 20, "需要审计目标仓位 shadow 结果时使用。"),
    "export_candidate_audit": ("导出与审计", 30, "需要审计候选目标仓位时使用。"),
    "export_history_snapshot": ("导出与审计", 40, "需要导出历史快照包做复核时使用。"),
    "project_check_current": ("开发验收", 10, "开发、提交或同步前使用；快速检查 current-only 项目状态。"),
    "ratio_only_check": ("开发验收", 20, "生成或修改 action plan 后使用；确认仍符合比例隐私边界。"),
    "research_first_check": ("开发验收", 30, "生成或修改 action plan 后使用；确认未绕过 ResearchFirst gate。"),
    "allocation_consistency_check": ("开发验收", 40, "生成 target allocation 或 intraday rules 后使用。"),
    "hidden_unicode_check": ("开发验收", 50, "提交前或 GitHub 提示 hidden Unicode warning 时使用。"),
    "web_check": ("开发验收", 60, "提交 Web 相关变更前使用；这是最完整的阻断式验收。"),
    "market_position_prompt": ("Codex 研究提示", 5, "需要把 Market Basis 更新到最新完整交易日时复制给 Codex。"),
    "strategy_briefing_prompt": ("Codex 研究提示", 10, "需要盘前策略简报时复制给 Codex；该任务需要研究上下文。"),
    "theme_research_prompt": ("Codex 研究提示", 20, "需要更新主线研究时复制给 Codex；通常需要数据源和人工判断。"),
    "etf_research_prompt": ("Codex 研究提示", 30, "需要为单只 ETF 补 ResearchFirst 档案时使用。"),
    "stock_research_prompt": ("Codex 研究提示", 40, "需要为单只个股补 profile、valuation、liquidity 时使用。"),
}


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        id="ingest_web_db",
        title="刷新 Web 数据库",
        category="Web",
        kind="script",
        impact="write_temp",
        description="从 latest_index.modules 导入当前状态到 temp/web_db，供网页读取。",
        display_command="python scripts/ingest_current_state.py",
        args=_py("scripts/ingest_current_state.py"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="web_check",
        title="完整 Web 验收",
        category="检查",
        kind="script",
        impact="check",
        description="运行 Web milestone 全量检查，包含 ingest、pytest、ratio-only、ResearchFirst 和导出扫描。",
        display_command="python scripts/web_check.py",
        args=_py("scripts/web_check.py"),
        timeout_seconds=900,
    ),
    ToolDefinition(
        id="project_check_current",
        title="项目当前态检查",
        category="检查",
        kind="script",
        impact="check",
        description="检查 current-only 项目状态，适合提交前快速确认。",
        display_command="python scripts/project_check.py --current-only",
        args=_py("scripts/project_check.py", "--current-only"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="hidden_unicode_check",
        title="隐藏 Unicode 检查",
        category="检查",
        kind="script",
        impact="check",
        description="扫描源码和文档中的隐藏格式控制字符。",
        display_command="python scripts/check_hidden_unicode.py",
        args=_py("scripts/check_hidden_unicode.py"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="build_latest_index",
        title="重建 latest_index",
        category="索引",
        kind="script",
        impact="write_research",
        description="只重建 research/latest_index.json 当前索引，不生成新的研究结论。",
        display_command="python scripts/build_latest_index.py",
        args=_py("scripts/build_latest_index.py"),
        timeout_seconds=180,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="ratio_only_check",
        title="Ratio-only 检查",
        category="检查",
        kind="script",
        impact="check",
        description="检查当前 action plan 是否仍遵守比例口径。",
        display_command="python scripts/check_ratio_only.py",
        args=_py("scripts/check_ratio_only.py"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="research_first_check",
        title="ResearchFirst 检查",
        category="检查",
        kind="script",
        impact="check",
        description="检查当前 action plan 的 ResearchFirst gate 是否通过。",
        display_command="python scripts/check_research_first_gate.py",
        args=_py("scripts/check_research_first_gate.py"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="allocation_consistency_check",
        title="仓位一致性检查",
        category="检查",
        kind="script",
        impact="check",
        description="检查 target allocation 与 intraday rules 的 bucket actual/target/gap 是否一致。",
        display_command="python scripts/check_cross_file_allocation_consistency.py",
        args=_py("scripts/check_cross_file_allocation_consistency.py"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="valuation_update_check",
        title="估值更新检查",
        category="盘前/盘中",
        kind="script",
        impact="write_research",
        description="检查估值报告缺失、过期或盘中跨区，并写入检查报告。",
        display_command="python scripts/check_valuation_updates.py --write-report",
        args=_py("scripts/check_valuation_updates.py", "--write-report"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="staleness_check",
        title="依赖陈旧检查",
        category="检查",
        kind="script",
        impact="write_research",
        description="检查当前研究依赖是否陈旧，并把状态同步到盘中规则。",
        display_command="python scripts/check_staleness.py --rebuild-index --write-report --update-intraday-rules",
        args=_py("scripts/check_staleness.py", "--rebuild-index", "--write-report", "--update-intraday-rules"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="generate_premarket_check",
        title="生成盘前执行检查",
        category="盘前/盘中",
        kind="script",
        impact="write_research",
        description="读取当前研究与操作建议，生成盘前执行检查和盘中监控清单。",
        display_command="python scripts/generate_premarket_check.py",
        args=_py("scripts/generate_premarket_check.py"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="generate_action_plan",
        title="生成操作建议",
        category="组合",
        kind="script",
        impact="write_research",
        description="从当前研究产物生成比例级 action plan，仍受 ResearchFirst gate 约束。",
        display_command="python scripts/generate_action_plan.py",
        args=_py("scripts/generate_action_plan.py"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="generate_target_allocation",
        title="生成目标仓位",
        category="组合",
        kind="script",
        impact="write_research",
        description="从当前市场、主线和组合输入生成目标仓位并同步盘中规则。",
        display_command="python scripts/generate_target_allocation.py --sync-intraday-rules",
        args=_py("scripts/generate_target_allocation.py", "--sync-intraday-rules"),
        timeout_seconds=240,
        post_success_steps=(
            ("refresh_latest_index", _py("scripts/build_latest_index.py"), 120),
        ),
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="generate_post_market_review",
        title="生成盘后复盘",
        category="盘后",
        kind="script",
        impact="write_research",
        description="基于当前本地研究生成日常盘后复盘草案。",
        display_command="python scripts/generate_post_market_review.py",
        args=_py("scripts/generate_post_market_review.py"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="generate_weekly_review",
        title="生成周度复盘",
        category="盘后",
        kind="script",
        impact="write_research",
        description="基于当前本地研究生成周度复盘草案。",
        display_command="python scripts/generate_post_market_review.py --review-type weekly",
        args=_py("scripts/generate_post_market_review.py", "--review-type", "weekly"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="audit_holdings_research",
        title="持仓 ResearchFirst 审计",
        category="ResearchFirst",
        kind="script",
        impact="write_research",
        description="审计当前持仓是否具备 profile、valuation、liquidity 等前置研究。",
        display_command="python scripts/audit_current_holdings_research.py",
        args=_py("scripts/audit_current_holdings_research.py"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="filter_current_backlog",
        title="过滤当前研究 backlog",
        category="ResearchFirst",
        kind="script",
        impact="write_research",
        description="按当前真实持仓过滤 ResearchFirst backlog。",
        display_command="python scripts/filter_current_research_backlog.py",
        args=_py("scripts/filter_current_research_backlog.py"),
        timeout_seconds=180,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="p2_position_review",
        title="P2 大持仓复核",
        category="ResearchFirst",
        kind="script",
        impact="write_research",
        description="生成比例口径的大持仓复核报告。",
        display_command="python scripts/generate_p2_position_review.py",
        args=_py("scripts/generate_p2_position_review.py"),
        timeout_seconds=180,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="theme_leaders",
        title="生成主线候选池",
        category="主题",
        kind="script",
        impact="write_research",
        description="根据主线登记册生成 ETF 和代表个股候选池，未完成研究的标的保持 ResearchFirst。",
        display_command="python scripts/generate_theme_leaders.py",
        args=_py("scripts/generate_theme_leaders.py"),
        timeout_seconds=240,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="valuation_reports",
        title="生成估值报告",
        category="估值",
        kind="script",
        impact="write_research",
        description="生成估值分区报告并同步盘中规则；批量运行可能耗时较长。",
        display_command="python scripts/generate_valuation_reports.py",
        args=_py("scripts/generate_valuation_reports.py"),
        timeout_seconds=600,
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="qmt_probe",
        title="QMT 只读连接探测",
        category="QMT",
        kind="script",
        impact="qmt_readonly",
        description="检查 QMT 只读连接状态，不写组合快照。",
        display_command="py -3.11 scripts/qmt_portfolio_snapshot.py --probe",
        args=_qmt_py("scripts/qmt_portfolio_snapshot.py", "--probe"),
        timeout_seconds=180,
        requires_qmt=True,
    ),
    ToolDefinition(
        id="qmt_snapshot",
        title="刷新 QMT 只读组合快照",
        category="QMT",
        kind="script",
        impact="write_research",
        description="从 QMT 只读接口刷新比例口径组合快照，并同步盘中规则。",
        display_command="py -3.11 scripts/qmt_portfolio_snapshot.py",
        args=_qmt_py("scripts/qmt_portfolio_snapshot.py"),
        timeout_seconds=240,
        requires_qmt=True,
        post_success_steps=(
            ("rebuild_target_allocation", _py("scripts/generate_target_allocation.py", "--sync-intraday-rules"), 240),
            ("refresh_latest_index", _py("scripts/build_latest_index.py"), 120),
        ),
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="intraday_once",
        title="盘中规则单次检查",
        category="QMT",
        kind="script",
        impact="qmt_readonly",
        description="用 QMT 行情对当前盘中规则做一次性检查。",
        display_command="py -3.11 scripts/intraday_dashboard.py --once-json",
        args=_qmt_py("scripts/intraday_dashboard.py", "--once-json"),
        timeout_seconds=180,
        requires_qmt=True,
    ),
    ToolDefinition(
        id="intraday_offline_once",
        title="盘中规则离线自检",
        category="盘前/盘中",
        kind="script",
        impact="check",
        description="QMT 不在线时，用规则参考价做一次离线自检。",
        display_command="py -3.11 scripts/intraday_dashboard.py --once-json --reference-fallback",
        args=_qmt_py("scripts/intraday_dashboard.py", "--once-json", "--reference-fallback"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="repair_portfolio_snapshot",
        title="修复组合快照质量",
        category="组合",
        kind="script",
        impact="write_research",
        description="基于最近保存的 QMT 快照生成修复后的比例口径组合快照。",
        display_command="python scripts/repair_portfolio_snapshot_quality.py",
        args=_py("scripts/repair_portfolio_snapshot_quality.py"),
        timeout_seconds=180,
        post_success_steps=(
            ("rebuild_target_allocation", _py("scripts/generate_target_allocation.py", "--sync-intraday-rules"), 240),
            ("refresh_latest_index", _py("scripts/build_latest_index.py"), 120),
        ),
        refresh_web_db_after=True,
    ),
    ToolDefinition(
        id="review_package",
        title="生成 Review Package",
        category="导出",
        kind="script",
        impact="write_temp",
        description="生成 current-only 外部审阅包，并执行隐私扫描。",
        display_command="python scripts/build_review_package.py --fail-on-privacy",
        args=_py("scripts/build_review_package.py", "--fail-on-privacy"),
        timeout_seconds=300,
    ),
    ToolDefinition(
        id="export_shadow",
        title="导出目标仓位 shadow",
        category="导出",
        kind="script",
        impact="write_temp",
        description="导出受控目标仓位 shadow 包到 temp。",
        display_command="python scripts/export_target_allocation_shadow.py --format zip --print-summary",
        args=_py("scripts/export_target_allocation_shadow.py", "--format", "zip", "--print-summary"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="export_candidate_audit",
        title="导出候选仓位审计",
        category="导出",
        kind="script",
        impact="write_temp",
        description="导出候选目标仓位审计包到 temp。",
        display_command="python scripts/export_target_allocation_candidate_audit.py --format zip --print-summary",
        args=_py("scripts/export_target_allocation_candidate_audit.py", "--format", "zip", "--print-summary"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="export_history_snapshot",
        title="导出历史快照",
        category="导出",
        kind="script",
        impact="write_temp",
        description="导出历史快照包到 temp。",
        display_command="python scripts/export_history_snapshot.py --format zip --print-summary",
        args=_py("scripts/export_history_snapshot.py", "--format", "zip", "--print-summary"),
        timeout_seconds=180,
    ),
    ToolDefinition(
        id="market_position_prompt",
        title="市场仓位更新提示词",
        category="Codex 研究",
        kind="prompt",
        impact="manual_prompt",
        description="复制给 Codex 后按 MARKET_POSITION 模块更新市场评分；只有最新完整交易日可用时才会推进 Market Basis。",
        prompt=(
            "请按 docs/modules/MARKET_POSITION.md 和 templates/market_score_template.md 更新市场仓位模块。"
            "读取 research/latest_index.json 的 modules 当前指针、research/config/market_position_mapping.json 和 docs/DATA_SOURCES.md，"
            "优先使用本地结构化数据源。只使用最新完整交易日作为 basis_trade_date；如果今天完整行情不可用，"
            "不要强行写成今天，请说明当前可用的最新完整交易日和原因。输出 research/market/market_score_YYYY-MM-DD_HHMMSS.md/json，"
            "并更新 research/latest_index.json 的 modules.market_score。市场评分、市场状态、权益和现金目标区间必须与 "
            "market_position_mapping 一致。保持 current-only、ratio-only 和 ResearchFirst 边界；不要修改 "
            "generate_action_plan.py 或 generate_target_allocation.py，不生成执行指令。完成后运行 "
            "python scripts/project_check.py --current-only，并告诉我下一步应生成 target allocation、action plan，然后刷新 Web 数据库。"
        ),
    ),
    ToolDefinition(
        id="strategy_briefing_prompt",
        title="盘前策略简报提示词",
        category="Codex 研究",
        kind="prompt",
        impact="manual_prompt",
        description="复制到 Codex 后生成盘前策略简报；该类研究需要外部信息和人工审阅。",
        prompt=(
            "请按 docs/DAILY_PROCESS.md 和 docs/modules/STRATEGY_BRIEFING.md 执行盘前策略简报。"
            "读取 latest_index 当前市场仓位、主线、组合、操作建议和估值状态。只按比例分析。"
        ),
    ),
    ToolDefinition(
        id="theme_research_prompt",
        title="主线研究提示词",
        category="Codex 研究",
        kind="prompt",
        impact="manual_prompt",
        description="复制到 Codex 后按主线研究模块生成 timestamped 主线报告。",
        prompt="请按 docs/modules/THEME_RESEARCH.md 更新主线研究，优先使用 Tushare 结构化数据，并写入 decision_log。",
    ),
    ToolDefinition(
        id="etf_research_prompt",
        title="ETF 研究提示词",
        category="Codex 研究",
        kind="prompt",
        impact="manual_prompt",
        description="复制到 Codex 后为指定 ETF 生成 ResearchFirst 前置档案。",
        prompt="请按 docs/modules/ETF_RESEARCH.md 为 <ETF代码> 生成 ETF 档案，优先使用 Tushare，并保持 ResearchFirst 边界。",
    ),
    ToolDefinition(
        id="stock_research_prompt",
        title="个股研究提示词",
        category="Codex 研究",
        kind="prompt",
        impact="manual_prompt",
        description="复制到 Codex 后为指定个股生成 profile、valuation、liquidity 前置研究。",
        prompt="请按 docs/modules/STOCK_RESEARCH.md 为 <股票代码> 生成个股档案，必须覆盖 profile、valuation、liquidity。",
    ),
)


class ToolConsoleService:
    extra_forbidden_text_re = re.compile(
        r"(total_asset|amount|market_value|shares|quantity|available_quantity|trade_amount|profit_amount|"
        r"account|full_account|order|fill|总资产|金额|市值|股数|数量|可用数量|交易金额|盈亏金额|账号|订单|成交)",
        re.IGNORECASE,
    )
    amount_unit_re = re.compile(r"[-+]?\d+(?:\.\d+)?\s*(?:元|万元|亿元|股|份)")

    def __init__(self, runner: Runner = subprocess.run) -> None:
        self.runner = runner
        self.tools = {definition.id: definition for definition in TOOL_DEFINITIONS}

    @staticmethod
    def _layout(tool: ToolDefinition) -> tuple[str, int, str]:
        return TOOL_LAYOUT.get(tool.id, ("其他", 999, "按需使用。"))

    @classmethod
    def _group_index(cls, group: str) -> int:
        try:
            return TOOL_GROUP_ORDER.index(group)
        except ValueError:
            return len(TOOL_GROUP_ORDER)

    @classmethod
    def _sort_key(cls, tool: ToolDefinition) -> tuple[int, int, str]:
        group, sequence, _when_to_use = cls._layout(tool)
        return (cls._group_index(group), sequence, tool.title)

    @classmethod
    def _tool_payload(cls, tool: ToolDefinition) -> dict[str, object]:
        group, sequence, when_to_use = cls._layout(tool)
        payload = tool.payload()
        payload.update(
            {
                "group": group,
                "sequence": sequence,
                "when_to_use": when_to_use,
            }
        )
        return payload

    def list_tools(self) -> dict[str, object]:
        sorted_tools = sorted(TOOL_DEFINITIONS, key=self._sort_key)
        categories = sorted({tool.category for tool in sorted_tools})
        groups = [group for group in TOOL_GROUP_ORDER if any(self._layout(tool)[0] == group for tool in sorted_tools)]
        groups.extend(sorted({self._layout(tool)[0] for tool in sorted_tools} - set(groups)))
        payload = {
            "summary": {
                "tool_count": len(TOOL_DEFINITIONS),
                "script_count": sum(1 for tool in TOOL_DEFINITIONS if tool.kind == "script"),
                "prompt_count": sum(1 for tool in TOOL_DEFINITIONS if tool.kind == "prompt"),
                "group_count": len(groups),
            },
            "groups": groups,
            "categories": categories,
            "tools": [self._tool_payload(tool) for tool in sorted_tools],
            "safety": {
                "whitelist_only": True,
                "arbitrary_command_input": False,
                "qmt_write_enabled": False,
                "trading_enabled": False,
            },
        }
        RatioOnlyService.assert_safe(payload)
        return payload

    def run_tool(self, tool_id: str) -> dict[str, object]:
        if tool_id not in self.tools:
            raise KeyError(tool_id)
        tool = self.tools[tool_id]
        if tool.kind == "prompt":
            payload = {
                "tool": self._tool_payload(tool),
                "status": "prompt",
                "message": "Copy the prompt into Codex to run this research workflow.",
                "prompt": tool.prompt,
                "steps": [],
            }
            RatioOnlyService.assert_safe(payload)
            return payload
        if tool.kind != "script" or not tool.args:
            payload = {
                "tool": self._tool_payload(tool),
                "status": "not_executable",
                "message": "This tool is listed for workflow reference only.",
                "steps": [],
            }
            RatioOnlyService.assert_safe(payload)
            return payload

        steps = [self._run_step("main", tool.args, tool.timeout_seconds)]
        if steps[0]["status"] == "passed":
            for step_name, step_args, timeout_seconds in tool.post_success_steps:
                steps.append(self._run_step(step_name, step_args, timeout_seconds))
                if steps[-1]["status"] != "passed":
                    break
        if all(step["status"] == "passed" for step in steps) and tool.refresh_web_db_after:
            steps.append(self._run_step("refresh_web_db", _py("scripts/ingest_current_state.py"), 180))
        status = "passed" if all(step["status"] == "passed" for step in steps) else "failed"
        payload = {
            "tool": self._tool_payload(tool),
            "status": status,
            "message": "Tool completed." if status == "passed" else "Tool failed. Review sanitized logs.",
            "steps": steps,
        }
        RatioOnlyService.assert_safe(payload)
        return payload

    def _run_step(self, name: str, args: Sequence[str], timeout_seconds: int) -> dict[str, object]:
        started = time.monotonic()
        try:
            completed = self.runner(
                list(args),
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                env=self._env(),
                shell=False,
            )
            status = "passed" if completed.returncode == 0 else "failed"
            step = {
                "name": name,
                "status": status,
                "exit_code": completed.returncode,
                "duration_seconds": round(time.monotonic() - started, 2),
                "stdout": self.sanitize_output(completed.stdout),
                "stderr": self.sanitize_output(completed.stderr),
            }
        except subprocess.TimeoutExpired as exc:
            step = {
                "name": name,
                "status": "failed",
                "exit_code": None,
                "duration_seconds": round(time.monotonic() - started, 2),
                "stdout": self.sanitize_output(exc.stdout or ""),
                "stderr": self.sanitize_output((exc.stderr or "") + "\nCommand timed out."),
            }
        RatioOnlyService.assert_safe(step)
        return step

    @staticmethod
    def _env() -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env.setdefault("PYTHONUTF8", "1")
        return env

    @classmethod
    def sanitize_output(cls, value: str | bytes | None, limit: int = 12000) -> str:
        if value is None:
            return ""
        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
        root_text = str(ROOT)
        text = text.replace(root_text, "[repo]")
        text = text.replace(root_text.replace("\\", "/"), "[repo]")
        text = RatioOnlyService.sanitize_text(text)
        text = cls.extra_forbidden_text_re.sub("[redacted_term]", text)
        text = cls.amount_unit_re.sub("[redacted_value]", text)
        if len(text) > limit:
            return text[:limit] + "\n[truncated]"
        return text
