#!/usr/bin/env python3
"""Realtime intraday battle map using QMT quotes and fixed local rules."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import intraday_monitor


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / "temp"
DEFAULT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
LATEST_INDEX = ROOT / "research" / "latest_index.json"
DEFAULT_WATCHLIST = ROOT / "research" / "config" / "intraday_watchlist.json"
DEFAULT_QMT_SITE = Path(r"D:\国金证券QMT交易端\python\Lib\site-packages")
RUNTIME_DIR = TEMP_ROOT / "runtime" / "alerts"

BUCKET_STYLE = {
    "cash_short": {"label": "现金/短融", "bg": "#eef2f7", "accent": "#5b6b7a"},
    "core_base": {"label": "宽基底仓", "bg": "#eaf2ff", "accent": "#2f6fbd"},
    "attack_mainline": {"label": "进攻主线仓", "bg": "#f2ecff", "accent": "#8b5cf6"},
    "defense": {"label": "防御仓", "bg": "#e8f7f1", "accent": "#0f8b6f"},
    "legacy_watch": {"label": "其他/待清理", "bg": "#fff4df", "accent": "#9a6700"},
}
BUCKET_ORDER = ["core_base", "attack_mainline", "defense", "legacy_watch", "cash_short"]
ALLOCATION_DISPLAY_ORDER = ["core_base", "attack_mainline", "defense", "legacy_watch", "cash_short"]
PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}
PRIORITY_LABELS = {"high": "高", "medium": "中", "low": "低", "none": "无"}
GATE_LABELS = {
    "risk_reduce_only": "只允许降风险",
    "verify_only": "只验证/观察",
    "allow_new_risk": "允许新增风险",
    "unknown": "门禁未知",
}
STALE_LABELS = {
    "fresh": "规则新鲜",
    "stale": "规则过期",
    "blocked": "规则阻断",
    "degraded": "规则降级",
    "legacy_unknown": "新鲜度未知",
}
SUMMARY_STATE_LABELS = {
    "triggered": "已触发",
    "near_trigger": "接近触发",
    "no_trigger": "未触发",
    "blocked": "前置缺失",
    "stale_blocked": "规则过期阻断",
    "gate_blocked": "门禁阻断",
}
ALERT_TYPE_LABELS = {
    "watch_trigger": "观察触发",
    "risk_trigger": "风险复核",
    "buy_trigger": "买入复核",
    "add_trigger": "加仓复核",
    "reduce_trigger": "减仓复核",
    "sell_trigger": "卖出复核",
    "near_trigger": "接近触发",
    "blocked": "前置缺失",
    "stale_blocked": "规则过期阻断",
    "gate_blocked": "门禁阻断",
    "invalidation_trigger": "失效复核",
}
ACTION_TYPE_LABELS = {
    "Add": "增配",
    "Reduce": "降配",
    "Hold": "持有",
    "Watch": "观察",
    "ResearchFirst": "先研究",
}
UI_TEXT_REPLACEMENTS = {
    "Target equity is": "目标权益仓位为",
    "actual equity is about": "当前权益约",
    "Allowed actions are ratio-only risk reduction and cash/short-duration restoration; no direct single-name add is allowed without fresh dossiers.": "只允许按比例降风险和恢复现金/短融仓；没有新鲜研究档案前，不允许直接单标的加仓。",
    "overall equity exposure": "总权益仓位",
    "cash/short-duration bucket": "现金/短融桶",
    "market score": "市场分数",
    "maps to equity": "对应权益仓位",
    "actual equity is above target upper bound": "当前权益高于目标上沿",
    "offensive add gate is not open": "进攻加仓门禁未打开",
    "cash/short-duration target is": "现金/短融目标为",
    "this is risk-reduction parking, not equity add exposure": "这是降风险后的停泊仓，不是新增权益风险",
    "legacy/watch target is zero or near zero in target allocation": "其他/待清理仓在目标配置中为零或接近零",
    "legacy/watch is a main source of equity deviation": "其他/待清理仓是权益偏离的主要来源",
    "Synced with latest target allocation; quality warnings block buy/add use.": "已同步最新目标配置；质量警告阻断买入/加仓使用。",
    "QMT open_price/cost field is non-positive; cost-based PnL is unavailable, but ratio-level portfolio analysis can continue.": "QMT 开盘价/成本字段为非正数，无法计算成本口径盈亏；比例级组合分析仍可继续。",
    "quality warnings block buy/add use": "质量警告阻断买入/加仓使用",
    "Normal": "常规",
    "Watch": "观察",
    "actionable": "有可复核动作",
    "watch": "观察",
}
ACTION_TEXT_REPLACEMENTS = {
    "reduce in stages before considering core adds": "分阶段降低，再考虑核心仓增配",
    "in stages before considering core adds": "分阶段处理，再考虑核心仓增配",
    " to ": " 至 ",
    "reduce": "降低",
    "increase": "增加",
    "add": "增加",
    "hold": "持有",
    "watch": "观察",
}
STANCE_COLOR = {
    "低估": "#16a34a",
    "价格低位": "#16a34a",
    "合理": "#475569",
    "价格合理": "#475569",
    "偏贵": "#d97706",
    "价格偏贵": "#d97706",
    "泡沫": "#b91c1c",
    "价格拥挤": "#b91c1c",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def parse_pct_range(text: str | None) -> tuple[float, float] | None:
    if not text or "-" not in text:
        return None
    left, right = text.replace("%", "").split("-", 1)
    try:
        return float(left), float(right)
    except ValueError:
        return None


def valuation_zone_for_value(visual: dict[str, Any], value: Any) -> dict[str, Any] | None:
    current = num(value)
    if current is None:
        return None
    zones = visual.get("zones", [])
    for zone in zones:
        if float(zone["min"]) <= current <= float(zone["max"]):
            return zone
    if not zones:
        return None
    return zones[0] if current < float(zones[0]["min"]) else zones[-1]


def valuation_zone_snapshot(visual: dict[str, Any], value: Any) -> dict[str, Any] | None:
    zone = valuation_zone_for_value(visual, value)
    if not zone:
        return None
    return {
        "key": zone.get("key"),
        "label": zone.get("label"),
        "min": zone.get("min"),
        "max": zone.get("max"),
        "color": zone.get("color"),
    }


def realtime_trend_visual(trend_visual: dict[str, Any] | None, last: Any) -> dict[str, Any] | None:
    if not trend_visual:
        return trend_visual
    current_raw = num(last)
    if current_raw is None:
        return trend_visual
    visual = copy.deepcopy(trend_visual)
    series = visual.get("price_series") or {}
    multiplier = num(series.get("realtime_price_multiplier"))
    if not series.get("comparable") or multiplier is None or multiplier <= 0:
        return visual
    current_comparable = current_raw * multiplier
    visual["current"] = round(current_comparable, 4)
    visual["realtime_overlay"] = {
        "raw_last": round(current_raw, 4),
        "comparable_last": round(current_comparable, 4),
        "multiplier": round(multiplier, 8),
        "basis_label": series.get("basis_label"),
        "factor_date": series.get("factor_date"),
    }
    drawdown = visual.get("drawdown") or {}
    rebound = visual.get("rebound") or {}
    high = num(drawdown.get("sample_high"))
    low = num(rebound.get("sample_low"))
    if high and high > 0:
        drawdown["from_sample_high_pct"] = round((current_comparable / high - 1) * 100, 2)
    if low and low > 0:
        rebound["from_sample_low_pct"] = round((current_comparable / low - 1) * 100, 2)
    visual["drawdown"] = drawdown
    visual["rebound"] = rebound
    return visual


def subject_bucket(subject: dict[str, Any]) -> str:
    return subject.get("allocation_bucket") or subject.get("reference_metrics", {}).get("allocation_bucket") or "legacy_watch"


def code_key(value: Any) -> str:
    return str(value or "").strip().upper().split(".", 1)[0]


def full_code_key(value: Any) -> str:
    return str(value or "").strip().upper()


def load_latest_portfolio_snapshot() -> tuple[dict[str, Any], Path | None]:
    path = latest_module_path("portfolio_snapshot")
    if not path or not path.exists():
        return {}, None
    return load_json(path), path


def portfolio_holding_codes(snapshot: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for item in snapshot.get("holdings", []):
        for key in ["ts_code", "code"]:
            value = item.get(key)
            if value:
                codes.add(code_key(value))
                codes.add(full_code_key(value))
    return codes


def load_intraday_watchlist(path: Path = DEFAULT_WATCHLIST) -> dict[str, Any]:
    if not path.exists():
        return {"include_codes": [], "hide_codes": []}
    return load_json(path)


def watchlist_codes(watchlist: dict[str, Any], key: str) -> set[str]:
    codes: set[str] = set()
    for value in watchlist.get(key, []):
        if isinstance(value, dict):
            raw = value.get("code") or value.get("ts_code")
        else:
            raw = value
        if raw:
            codes.add(code_key(raw))
            codes.add(full_code_key(raw))
    return codes


def filter_rules_for_monitor_pool(rules: dict[str, Any]) -> dict[str, Any]:
    snapshot, snapshot_path = load_latest_portfolio_snapshot()
    holding_codes = portfolio_holding_codes(snapshot)
    watchlist = load_intraday_watchlist()
    include_codes = watchlist_codes(watchlist, "include_codes")
    hide_codes = watchlist_codes(watchlist, "hide_codes")

    if not holding_codes and not include_codes:
        scoped = dict(rules)
        scoped["monitor_scope"] = {
            "mode": "rules_all_due_missing_portfolio_snapshot",
            "portfolio_snapshot_file": str(snapshot_path.relative_to(ROOT)).replace("\\", "/") if snapshot_path else None,
            "watchlist_file": str(DEFAULT_WATCHLIST.relative_to(ROOT)).replace("\\", "/") if DEFAULT_WATCHLIST.exists() else None,
            "source_subject_count": len(rules.get("subjects", [])),
            "active_subject_count": len(rules.get("subjects", [])),
            "hidden_subjects": [],
        }
        return scoped

    subjects = []
    hidden = []
    for subject in rules.get("subjects", []):
        code = subject.get("code")
        keys = {code_key(code), full_code_key(code)}
        is_holding = bool(keys & holding_codes)
        is_watch = bool(keys & include_codes)
        is_hidden = bool(keys & hide_codes)
        if is_holding or (is_watch and not is_hidden):
            kept = dict(subject)
            kept["monitor_source"] = "真实持仓" if is_holding else "显式观察"
            subjects.append(kept)
        else:
            hidden.append(
                {
                    "code": code,
                    "name": subject.get("name"),
                    "reason": "不在最新真实持仓，也不在盘中显式观察池",
                }
            )

    scoped = dict(rules)
    scoped["subjects"] = subjects
    scoped["monitor_scope"] = {
        "mode": "holdings_plus_explicit_watchlist",
        "portfolio_snapshot_file": str(snapshot_path.relative_to(ROOT)).replace("\\", "/") if snapshot_path else None,
        "watchlist_file": str(DEFAULT_WATCHLIST.relative_to(ROOT)).replace("\\", "/") if DEFAULT_WATCHLIST.exists() else None,
        "source_subject_count": len(rules.get("subjects", [])),
        "active_subject_count": len(subjects),
        "holding_code_count": len({code_key(code) for code in holding_codes if "." not in code}),
        "explicit_watch_count": len({code_key(code) for code in include_codes if "." not in code}),
        "hidden_subjects": hidden,
    }
    return scoped


def subject_attribute_tags(subject: dict[str, Any], quote: dict[str, Any] | None = None) -> list[str]:
    """Display research attributes separately from the allocation bucket."""
    code = str(subject.get("code") or (quote or {}).get("code") or "")
    group = str(subject.get("group") or "")
    role = str(subject.get("role") or "")
    bucket = subject_bucket(subject)
    stance = ((quote or {}).get("security_stance") or subject.get("security_stance") or {})
    stance_label = str(stance.get("label") or "")
    text = f"{group} {role}"
    if code == "159201.SZ":
        return ["权益防御", "质量现金流", "因子策略"]
    if code == "002352.SZ":
        return ["质量修复", "绩优超跌", "物流龙头", "单股风险"]
    tags: list[str] = []

    def add(label: str) -> None:
        if label and label not in tags:
            tags.append(label)

    if bucket == "core_base":
        add("宽基底仓")
    if bucket == "defense" or any(key in text for key in ["防御", "红利", "公用事业", "金融", "医药"]):
        add("防御属性")
    if bucket == "attack_mainline" or "进攻" in text:
        add("进攻属性")
    if bucket == "legacy_watch" or "待清理" in text or "遗留" in text:
        add("待清理观察")

    if "价格低位" in stance_label and "核心质量" in text:
        add("超跌修复观察")
    if "价格低位" in stance_label and "超跌修复观察" not in tags:
        add("低位观察")

    return tags[:4]


def display_action_type(value: Any) -> str:
    text = str(value or "-")
    return ACTION_TYPE_LABELS.get(text, text)


def display_ui_text(value: Any) -> str:
    text = str(value or "-")
    for source, target in UI_TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    return text


def staleness_tooltip(stale: dict[str, Any]) -> str:
    reason = str(stale.get("reason") or "").strip()
    if not reason or "???" in reason:
        status = str(stale.get("status") or "legacy_unknown")
        fallback = {
            "fresh": "规则依赖检查通过；盘中窗口仅用于观察和风险复核，具体买卖仍以 ACTION_PLAN 为准。",
            "stale": "规则依赖已过期；盘中窗口仅供观察，不能作为买入或加仓依据。",
            "blocked": "规则被阻断；缺少必要上游数据或检查未通过。",
            "degraded": "规则处于降级状态；只能用于观察和风险复核。",
            "legacy_unknown": "缺少规则状态信息；仅供观察。",
        }
        reason = fallback.get(status, "缺少规则状态信息；仅供观察。")
    return display_ui_text(reason).replace("ACTION_PLAN?", "ACTION_PLAN。")


def display_action_text(value: Any) -> str:
    text = display_ui_text(value)
    for source, target in ACTION_TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    return text.replace("pp", "个百分点")


def latest_module_path(module: str) -> Path | None:
    index = load_json(LATEST_INDEX) if LATEST_INDEX.exists() else {}
    record = (index.get("modules") or {}).get(module) or {}
    path = record.get("path")
    return ROOT / path if path else None


def load_latest_action_plan() -> dict[str, Any]:
    path = latest_module_path("action_plan")
    if not path or not path.exists():
        return {}
    data = load_json(path)
    data["_source_path"] = path.relative_to(ROOT).as_posix()
    return data


def action_bucket(action: dict[str, Any]) -> str | None:
    role = str(action.get("bucket_role") or "").lower()
    subject_name = str((action.get("subject") or {}).get("name") or "")
    if role in {"bond_cash", "cash_short"} or "现金" in subject_name or "短融" in subject_name:
        return "cash_short"
    if role in {"core", "core_base"} or "核心" in subject_name or "宽基" in subject_name:
        return "core_base"
    if role in {"offensive", "attack_mainline"} or "进攻" in subject_name:
        return "attack_mainline"
    if role in {"defensive", "defense"} or "防御" in subject_name:
        return "defense"
    if role in {"theme", "legacy_watch"} or "待清理" in subject_name or "legacy" in subject_name:
        return "legacy_watch"
    return None


def action_plan_context(action_plan: dict[str, Any]) -> dict[str, Any]:
    if not action_plan:
        return {}
    bucket_actions: dict[str, list[dict[str, Any]]] = {}
    for action in action_plan.get("actions", []):
        bucket = action_bucket(action)
        if bucket:
            bucket_actions.setdefault(bucket, []).append(
                {
                    "priority": action.get("priority"),
                    "action_type": action.get("action_type"),
                    "subject": (action.get("subject") or {}).get("name"),
                    "suggested_change": action.get("suggested_change"),
                    "target_position": action.get("target_position"),
                    "strength": action.get("recommendation_strength"),
                }
            )
    return {
        "source_path": action_plan.get("_source_path"),
        "generated_at": action_plan.get("generated_at"),
        "summary": action_plan.get("summary", {}),
        "bucket_actions": bucket_actions,
        "intraday_triggers": action_plan.get("intraday_triggers", []),
        "hard_constraints": action_plan.get("triggered_hard_constraints", []),
    }


class LongToolTipFilter(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.current_widget: QWidget | None = None
        self.popup = QLabel()
        self.popup.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.popup.setWordWrap(True)
        self.popup.setMinimumWidth(260)
        self.popup.setMaximumWidth(560)
        self.popup.setStyleSheet(
            """
            QLabel {
                background: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 12px;
                line-height: 1.4;
            }
            """
        )

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override.
        if not isinstance(obj, QWidget):
            return super().eventFilter(obj, event)

        if event.type() in {QEvent.Type.Enter, QEvent.Type.ToolTip}:
            if obj.toolTip():
                self._show_for(obj)
                return True

        if event.type() == QEvent.Type.MouseMove and obj is self.current_widget and self.popup.isVisible():
            self._move_popup()
            return False

        if event.type() in {QEvent.Type.Leave, QEvent.Type.Hide} and obj is self.current_widget:
            self.popup.hide()
            self.current_widget = None

        return super().eventFilter(obj, event)

    def _show_for(self, widget: QWidget) -> None:
        self.current_widget = widget
        self.popup.setText(widget.toolTip())
        self.popup.adjustSize()
        self._move_popup()
        self.popup.show()

    def _move_popup(self) -> None:
        self.popup.move(QCursor.pos() + QPoint(18, 22))


class ValuationMapBar(QWidget):
    """Four-zone valuation map with current, support, right-confirm, and risk markers."""

    def __init__(
        self,
        visual: dict[str, Any],
        markers: dict[str, Any],
        current_value: Any,
        bg_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.visual = visual
        self.markers = markers
        self.current_value = current_value
        self.bg_color = bg_color
        self.setMinimumHeight(82)
        self.setToolTip(self.tooltip_text())

    def tooltip_text(self) -> str:
        zone = valuation_zone_for_value(self.visual, self.current_value)
        series = self.visual.get("price_series") or {}
        parts = [
            f"当前位置：{zone.get('label', '-') if zone else '-'}",
            f"当前价格/净值：{fmt(self.current_value, 4)}",
            "黑色竖线：实时当前位置",
        ]
        if series:
            parts.append(f"历史比较口径：{series.get('basis_label') or series.get('basis') or '-'}")
            parts.append(series.get("note") or "估值带已折算到当前场内价格尺度。")
        for key in ["support", "right_confirm", "risk_zone_start"]:
            marker = self.markers.get(key) or {}
            if marker.get("value") is not None:
                parts.append(f"{marker.get('label', key)}：{fmt(marker.get('value'), 4)}")
        parts.append("风控位：跌破或接近后优先复核风险，不等于自动卖出。")
        parts.append("右侧确认：重新站回后才考虑由观察转配置，不等于自动买入。")
        return "\n".join(parts)

    def _scale(self, value: float, minimum: float, maximum: float, rect: QRectF) -> float:
        if maximum <= minimum:
            return rect.left()
        ratio = min(1.0, max(0.0, (value - minimum) / (maximum - minimum)))
        return rect.left() + rect.width() * ratio

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt override.
        zones = self.visual.get("zones", [])
        if not zones:
            return
        minimum = float(zones[0]["min"])
        maximum = float(zones[-1]["max"])
        current = num(self.current_value)
        marker_values = [num((self.markers.get(key) or {}).get("value")) for key in ["support", "right_confirm", "risk_zone_start"]]
        all_values = [minimum, maximum] + [value for value in marker_values if value is not None]
        if current is not None:
            all_values.append(current)
        minimum, maximum = min(all_values), max(all_values)
        padding = max((maximum - minimum) * 0.04, 0.0001)
        minimum -= padding
        maximum += padding

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.bg_color))
        rect = QRectF(12, 17, self.width() - 24, 18)

        for zone in zones:
            left = self._scale(float(zone["min"]), minimum, maximum, rect)
            right = self._scale(float(zone["max"]), minimum, maximum, rect)
            painter.fillRect(QRectF(left, rect.top(), max(2, right - left), rect.height()), QColor(zone.get("color", "#cccccc")))

        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(rect, 5, 5)

        marker_specs = [
            ("support", "#2563eb"),
            ("right_confirm", "#06b6d4"),
            ("risk_zone_start", "#dc2626"),
        ]
        for key, fallback_color in marker_specs:
            marker = self.markers.get(key) or {}
            value = num(marker.get("value"))
            if value is None:
                continue
            x = self._scale(value, minimum, maximum, rect)
            color = QColor(marker.get("color") or fallback_color)
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            if key == "support":
                poly = QPolygonF([QPointF(x, rect.bottom() + 12), QPointF(x - 6, rect.bottom() + 2), QPointF(x + 6, rect.bottom() + 2)])
                painter.drawPolygon(poly)
            elif key == "right_confirm":
                poly = QPolygonF([QPointF(x, rect.top() - 9), QPointF(x + 6, rect.top() - 3), QPointF(x, rect.top() + 3), QPointF(x - 6, rect.top() - 3)])
                painter.drawPolygon(poly)
            else:
                painter.drawLine(int(x), int(rect.top() - 8), int(x), int(rect.bottom() + 8))

        if current is not None:
            x = self._scale(current, minimum, maximum, rect)
            painter.setPen(QPen(QColor("#0f172a"), 3))
            painter.drawLine(int(x), int(rect.top() - 10), int(x), int(rect.bottom() + 12))
            painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(max(0, x - 34), rect.bottom() + 12, 68, 16), Qt.AlignmentFlag.AlignCenter, fmt(current, 3))


class TrendStrip(QWidget):
    def __init__(self, trend_visual: dict[str, Any] | None, bg_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.trend_visual = trend_visual or {}
        self.bg_color = bg_color
        self.setMinimumHeight(82)
        self.setToolTip(self.tooltip_text())

    def tooltip_text(self) -> str:
        if not self.trend_visual.get("available"):
            return "趋势数据不足"
        lines = []
        for item in self.trend_visual.get("trends", []):
            lines.append(f"{item.get('label')}趋势：{item.get('state')}，{item.get('window_days')}日变化 {fmt(item.get('change_pct'))}%")
        return "\n".join(lines)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.bg_color))
        items = self.trend_visual.get("trends", [])
        if not items:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "趋势不足")
            return
        labels = {"long": "长", "mid": "中", "short": "短"}
        width = (self.width() - 24) / 3
        for idx, item in enumerate(items[:3]):
            rect = QRectF(8 + idx * width, 8, width - 6, 40)
            state = item.get("state", "-")
            color = QColor("#dc2626" if state == "上行" else ("#16a34a" if state == "下行" else "#f59e0b"))
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#d9e2ef"), 1))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QPen(color, 3))
            if state == "上行":
                painter.drawLine(QPointF(rect.left() + 12, rect.bottom() - 11), QPointF(rect.right() - 12, rect.top() + 11))
                painter.drawLine(QPointF(rect.right() - 12, rect.top() + 11), QPointF(rect.right() - 19, rect.top() + 11))
                painter.drawLine(QPointF(rect.right() - 12, rect.top() + 11), QPointF(rect.right() - 12, rect.top() + 18))
            elif state == "下行":
                painter.drawLine(QPointF(rect.left() + 12, rect.top() + 11), QPointF(rect.right() - 12, rect.bottom() - 11))
                painter.drawLine(QPointF(rect.right() - 12, rect.bottom() - 11), QPointF(rect.right() - 19, rect.bottom() - 11))
                painter.drawLine(QPointF(rect.right() - 12, rect.bottom() - 11), QPointF(rect.right() - 12, rect.bottom() - 18))
            else:
                mid_y = rect.center().y()
                painter.drawLine(QPointF(rect.left() + 12, mid_y), QPointF(rect.right() - 12, mid_y))
            painter.setPen(QColor("#334155"))
            painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
            trend_key = labels.get(item.get("key"), item.get("label", "-")[:1])
            painter.drawText(QRectF(rect.left(), rect.bottom() - 16, rect.width(), 14), Qt.AlignmentFlag.AlignCenter, f"{trend_key} {state}")


class MoveMap(QWidget):
    def __init__(self, trend_visual: dict[str, Any] | None, bg_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.trend_visual = trend_visual or {}
        self.bg_color = bg_color
        self.setMinimumHeight(82)
        self.setToolTip(self.tooltip_text())

    def tooltip_text(self) -> str:
        if not self.trend_visual.get("available"):
            return "回撤/反弹样本不足"
        dd = self.trend_visual.get("drawdown", {})
        rb = self.trend_visual.get("rebound", {})
        series = self.trend_visual.get("price_series") or {}
        overlay = self.trend_visual.get("realtime_overlay") or {}
        lines = []
        if series:
            lines.append(f"历史口径：{series.get('basis_label') or series.get('basis') or '-'}")
            if not series.get("comparable"):
                lines.append("注意：当前为未复权代理，长期前高/前低不可直接作为强判断。")
        if overlay:
            lines.append(
                f"盘中换算：场内价 {fmt(overlay.get('raw_last'), 4)} × {fmt(overlay.get('multiplier'), 4)} = "
                f"{fmt(overlay.get('comparable_last'), 4)}（{overlay.get('basis_label') or '-'}）"
            )
        lines.extend(
            [
                f"前高：{fmt(dd.get('sample_high'), 4)}（{dd.get('sample_high_date') or '-'}）",
                f"从前高至今回撤：{fmt(dd.get('from_sample_high_pct'))}%",
                f"常见120日回撤：{fmt(dd.get('common_120d_drawdown_pct'))}%，深度回撤参考：{fmt(dd.get('deep_120d_drawdown_pct'))}%，极值：{fmt(dd.get('max_120d_drawdown_pct'))}%",
                f"前低：{fmt(rb.get('sample_low'), 4)}（{rb.get('sample_low_date') or '-'}）",
                f"从前低至今涨幅：{fmt(rb.get('from_sample_low_pct'))}%",
                f"常见120日反弹：{fmt(rb.get('common_120d_rebound_pct'))}%，强反弹参考：{fmt(rb.get('strong_120d_rebound_pct'))}%，极值：{fmt(rb.get('max_120d_rebound_pct'))}%",
            ]
        )
        return "\n".join(
            lines
        )

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.bg_color))
        if not self.trend_visual.get("available"):
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "波动不足")
            return
        dd = self.trend_visual.get("drawdown", {})
        rb = self.trend_visual.get("rebound", {})
        drawdown = abs(num(dd.get("from_sample_high_pct")) or 0)
        common_dd = abs(num(dd.get("common_120d_drawdown_pct")) or 0)
        deep_dd = abs(num(dd.get("deep_120d_drawdown_pct")) or common_dd)
        max_dd = abs(num(dd.get("max_120d_drawdown_pct")) or deep_dd or drawdown or 1)
        rebound = num(rb.get("from_sample_low_pct")) or 0
        common_rb = num(rb.get("common_120d_rebound_pct")) or 0
        strong_rb = num(rb.get("strong_120d_rebound_pct")) or common_rb
        max_rb = num(rb.get("max_120d_rebound_pct")) or strong_rb or rebound or 1

        gauges = [
            ("最大回撤", drawdown, common_dd, deep_dd, max(max_dd, drawdown, 1), "#16a34a"),
            ("最大反弹", rebound, common_rb, strong_rb, max(max_rb, rebound, 1), "#dc2626"),
        ]
        painter.setFont(QFont("Microsoft YaHei", 8))
        for idx, (label, value, normal, strong, scale, color) in enumerate(gauges):
            box = QRectF(8, 8 + idx * 36, self.width() - 16, 30)
            label_rect = QRectF(box.left(), box.top(), 60, 14)
            bar = QRectF(box.left() + 62, box.top() + 4, max(30, box.width() - 118), 12)
            painter.setPen(QColor("#334155"))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignLeft, label)
            painter.setBrush(QColor("#d7dee8"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar, 6, 6)

            normal_x = self._x_for_horizontal(bar, normal, scale)
            strong_x = self._x_for_horizontal(bar, strong, scale)
            zone_left = min(normal_x, strong_x)
            zone_w = abs(strong_x - normal_x)
            painter.setBrush(QColor("#fde68a"))
            painter.drawRect(QRectF(zone_left, bar.top(), max(2, zone_w), bar.height()))

            current_x = self._x_for_horizontal(bar, value, scale)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(bar.left(), bar.top(), max(2, current_x - bar.left()), bar.height()), 6, 6)
            painter.setPen(QPen(QColor("#111827"), 2))
            painter.drawLine(int(current_x), int(bar.top() - 5), int(current_x), int(bar.bottom() + 5))
            painter.setPen(QColor("#334155"))
            painter.drawText(QRectF(bar.right() + 6, box.top() + 1, 52, 18), Qt.AlignmentFlag.AlignLeft, f"{value:.1f}%")
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(bar.left(), bar.bottom() + 1, bar.width(), 12), Qt.AlignmentFlag.AlignRight, f"极值 {scale:.1f}%")

    def _x_for_horizontal(self, rect: QRectF, value: float, scale: float) -> float:
        ratio = min(1.0, max(0.0, value / scale if scale else 0.0))
        return rect.left() + rect.width() * ratio


class PositionGapBar(QWidget):
    def __init__(self, current_pct: Any, target_range: str | None, bg_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_pct = num(current_pct) or 0.0
        self.target_range = target_range
        self.bg_color = bg_color
        self.setMinimumHeight(82)
        self.setToolTip(self.tooltip_text())

    def tooltip_text(self) -> str:
        rng = parse_pct_range(self.target_range)
        if not rng:
            return f"当前仓位：{fmt(self.current_pct)}%，目标仓位：{self.target_range or '-'}"
        low, high = rng
        gap = 0.0 if low <= self.current_pct <= high else (self.current_pct - high if self.current_pct > high else self.current_pct - low)
        return f"当前仓位：{fmt(self.current_pct)}%\n目标区间：{low:g}%-{high:g}%\n偏离：{gap:+.2f}个百分点"

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.bg_color))
        rect = QRectF(12, 21, self.width() - 24, 12)
        rng = parse_pct_range(self.target_range)
        target_low, target_high = rng if rng else (0.0, max(1.0, self.current_pct))
        scale_max = max(target_high * 1.4, self.current_pct * 1.2, 3.0)
        painter.setBrush(QColor("#d7dee8"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 6, 6)
        left = rect.left() + rect.width() * target_low / scale_max
        right = rect.left() + rect.width() * target_high / scale_max
        painter.setBrush(QColor("#60a5fa"))
        painter.drawRoundedRect(QRectF(left, rect.top(), max(2, right - left), rect.height()), 6, 6)
        current_x = rect.left() + rect.width() * min(1.0, self.current_pct / scale_max)
        painter.setPen(QPen(QColor("#111827"), 3))
        painter.drawLine(int(current_x), int(rect.top() - 8), int(current_x), int(rect.bottom() + 8))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(QRectF(0, 34, self.width(), 16), Qt.AlignmentFlag.AlignCenter, f"{self.current_pct:.2f}% / {self.target_range or '-'}")


class AllocationMap(QWidget):
    def __init__(self, allocation: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.allocation = allocation or {}
        self.setMinimumHeight(124)
        self.setToolTip(self.tooltip_text())

    def tooltip_text(self) -> str:
        if not self.allocation:
            return "未找到仓位底图"
        lines = [
            f"目标权益：{fmt(self.allocation.get('target_equity_pct'))}%，目标现金短融：{fmt(self.allocation.get('target_cash_short_pct'))}%",
            f"实际权益：{fmt(self.allocation.get('actual_equity_pct'))}%，实际现金短融：{fmt(self.allocation.get('actual_cash_short_pct'))}%",
            self.allocation.get("bucket_model", ""),
        ]
        for item in self.allocation.get("buckets", []):
            lines.append(f"{item.get('label')}：目标 {fmt(item.get('target_pct'))}%，实际 {fmt(item.get('actual_pct'))}%，差 {fmt(item.get('gap_pct'))}个百分点")
        for item in self.allocation.get("missing_upstream", []):
            lines.append(f"缺失上游：{item.get('module')} 需输出 {item.get('missing')}")
        return "\n".join(lines)

    def update_allocation(self, allocation: dict[str, Any]) -> None:
        self.allocation = allocation
        self.setToolTip(self.tooltip_text())
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0f172a"))
        painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        painter.setPen(QColor("#e5eefb"))
        painter.drawText(18, 24, "理想仓位桶")
        if not self.allocation:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "未找到最新仓位底图")
            return

        x, width = 18, self.width() - 36
        bucket_row = QRectF(x, 42, width, 28)
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(x, 24, width, 16), Qt.AlignmentFlag.AlignLeft, "权益仓位桶在前，现金/短融在后；真实持仓仅作覆盖标记")

        ideal_segments_raw = [
            {"label": item.get("label"), "pct": item.get("target_pct"), "color": item.get("color")}
            for item in self.allocation.get("ideal_segments", [])
            if (num(item.get("target_pct")) or 0) > 0
        ]
        ideal_segments = self._ordered_segments(ideal_segments_raw)
        self._draw_segments(painter, bucket_row, ideal_segments, "pct")

        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(x, 78, width, 16), Qt.AlignmentFlag.AlignLeft, "真实持仓覆盖")
        self._draw_actual_overlay(painter, QRectF(x, 94, width, 10))

    def _ordered_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def rank(item: dict[str, Any]) -> int:
            label = str(item.get("label", ""))
            if "现金" in label or "短融" in label:
                return ALLOCATION_DISPLAY_ORDER.index("cash_short")
            if "宽基" in label or "核心" in label:
                return ALLOCATION_DISPLAY_ORDER.index("core_base")
            if "进攻" in label or "主线" in label:
                return ALLOCATION_DISPLAY_ORDER.index("attack_mainline")
            if "防御" in label:
                return ALLOCATION_DISPLAY_ORDER.index("defense")
            return ALLOCATION_DISPLAY_ORDER.index("legacy_watch")

        return sorted(segments, key=rank)

    def _draw_segments(self, painter: QPainter, rect: QRectF, segments: list[dict[str, Any]], pct_key: str) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#263447"))
        painter.drawRoundedRect(rect, 7, 7)
        cursor = rect.left()
        total = sum(num(item.get(pct_key)) or 0 for item in segments) or 100.0
        for item in segments:
            pct = num(item.get(pct_key)) or 0
            if pct <= 0:
                continue
            seg_w = rect.width() * pct / total
            seg = QRectF(cursor, rect.top(), seg_w, rect.height())
            painter.setBrush(QColor(item.get("color", "#94a3b8")))
            painter.drawRoundedRect(seg, 7, 7)
            painter.setPen(QColor("#f8fafc"))
            painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
            label = f"{item.get('label', '-')}\n{pct:.1f}%"
            painter.drawText(seg.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignCenter, label)
            painter.setPen(Qt.PenStyle.NoPen)
            cursor += seg_w

    def _draw_actual_overlay(self, painter: QPainter, rect: QRectF) -> None:
        painter.setBrush(QColor("#263447"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 5, 5)
        cursor = rect.left()
        for item in sorted(self.allocation.get("actual_overlay", []), key=lambda item: ALLOCATION_DISPLAY_ORDER.index(item.get("key", "legacy_watch")) if item.get("key") in ALLOCATION_DISPLAY_ORDER else 99):
            actual = num(item.get("actual_pct")) or 0
            if actual <= 0:
                continue
            seg_w = rect.width() * min(actual, 100.0) / 100.0
            painter.setBrush(QColor(item.get("color", "#94a3b8")))
            painter.drawRoundedRect(QRectF(cursor, rect.top(), seg_w, rect.height()), 5, 5)
            cursor += seg_w

        cursor = rect.left()
        painter.setFont(QFont("Microsoft YaHei", 8))
        for item in sorted(self.allocation.get("actual_overlay", []), key=lambda item: ALLOCATION_DISPLAY_ORDER.index(item.get("key", "legacy_watch")) if item.get("key") in ALLOCATION_DISPLAY_ORDER else 99):
            actual = num(item.get("actual_pct")) or 0
            if actual <= 0:
                continue
            seg_w = rect.width() * min(actual, 100.0) / 100.0
            gap = num(item.get("gap_pct")) or 0
            color = "#fecaca" if gap > 1 else ("#bbf7d0" if gap < -1 else "#e5eefb")
            painter.setPen(QColor(color))
            painter.drawText(QRectF(cursor, rect.bottom() + 2, max(64, seg_w), 16), Qt.AlignmentFlag.AlignLeft, f"{item.get('label')} {actual:.1f}%")
            cursor += seg_w


class ActionPlanPanel(QFrame):
    def __init__(self, action_plan: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_plan = action_plan or {}
        self.setObjectName("bucketFrame")
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)
        if not self.action_plan:
            label = QLabel("今日操作建议：未找到最新操作计划")
            label.setStyleSheet("color:#b91c1c; font-weight:700;")
            layout.addWidget(label)
            return
        summary = self.action_plan.get("summary", {})
        title = QLabel(
            "今日操作建议｜{state} / {strength}".format(
                state=display_ui_text(summary.get("action_state", "-")),
                strength=display_ui_text(summary.get("recommendation_strength", "-")),
            )
        )
        title.setStyleSheet("font-size:14px; font-weight:700; color:#0f172a;")
        title.setToolTip(f"来源：{self.action_plan.get('_source_path', '-')}\n生成：{self.action_plan.get('generated_at', '-')}")
        layout.addWidget(title)
        line = QLabel(display_ui_text(summary.get("one_line_conclusion", "")))
        line.setWordWrap(True)
        line.setStyleSheet("color:#334155;")
        layout.addWidget(line)
        chips = QHBoxLayout()
        for action in self.action_plan.get("actions", [])[:6]:
            bucket = action_bucket(action) or "legacy_watch"
            style = BUCKET_STYLE.get(bucket, BUCKET_STYLE["legacy_watch"])
            subject = display_ui_text((action.get("subject") or {}).get("name") or "-")
            text = f"{display_action_type(action.get('action_type'))}｜{subject}｜{display_action_text(action.get('suggested_change'))}"
            chip = QLabel(text)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setStyleSheet(f"background:{style['bg']}; color:#0f172a; border-left:4px solid {style['accent']}; border-radius:6px; padding:6px 8px; font-weight:700;")
            chip.setToolTip(
                "\n".join(
                    [
                        f"对象：{subject}",
                        f"目标：{action.get('target_position') or '-'}",
                        f"强度：{display_action_text(action.get('recommendation_strength') or '-')}",
                        "证据：" + "；".join(display_ui_text(item) for item in action.get("evidence", [])[:3]),
                    ]
                )
            )
            chips.addWidget(chip)
        chips.addStretch(1)
        layout.addLayout(chips)

    def update_action_plan(self, action_plan: dict[str, Any]) -> None:
        self.action_plan = action_plan
        while self.layout() and self.layout().count():
            item = self.layout().takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._build()

def build_snapshot_from_rules(rules: dict[str, Any], ticks: dict[str, dict[str, Any]], action_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    quotes: dict[str, dict[str, Any]] = {}
    expected_codes = [item["code"] for item in rules.get("subjects", [])]
    received_codes = []
    timetags = []
    for subject in rules.get("subjects", []):
        code = subject["code"]
        ref = subject.get("reference_metrics", {})
        live = ticks.get(code, {})
        last = live.get("last")
        visual = ref.get("valuation_visual") or {}
        realtime_zone = valuation_zone_snapshot(visual, last)
        trend_visual = realtime_trend_visual(ref.get("trend_visual"), last)
        report_zone_key = visual.get("current_zone")
        if num(last) is not None:
            received_codes.append(code)
        if live.get("qmt_timetag"):
            timetags.append(str(live.get("qmt_timetag")))
        quote = {
            "name": subject.get("name", code),
            "type": subject.get("type", "unknown"),
            "last": last,
            "pre_close": live.get("pre_close"),
            "pct_chg": live.get("pct_chg"),
            "qmt_timetag": live.get("qmt_timetag"),
            "valuation_visual": visual,
            "realtime_valuation_zone": realtime_zone,
            "valuation_zone_changed": bool(realtime_zone and report_zone_key and realtime_zone.get("key") != report_zone_key),
            "valuation_report_zone": {
                "key": report_zone_key,
                "label": visual.get("current_zone_label"),
                "value": visual.get("current_value"),
                "price_date": ref.get("price_date"),
                "source_profile": subject.get("source_profile"),
            },
            "trend_visual": trend_visual,
            "risk_markers": ref.get("risk_markers"),
            "security_stance": subject.get("security_stance") or ref.get("security_stance"),
            "allocation_bucket": subject_bucket(subject),
            "position_visual": {
                "current_position_pct": ref.get("current_position_pct"),
                "target_position_range": ref.get("target_position_range"),
                "last_reference": ref.get("last_reference"),
            },
            "support": ref.get("support"),
            "right_confirm": ref.get("right_confirm"),
            "risk_zone_start": ref.get("risk_zone_start"),
        }
        quotes[code] = quote
    allocation_map = rules.get("allocation_map") or {}
    return {
        "module": "intraday_quotes_snapshot",
        "version": "1.2",
        "timestamp": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "source": "qmt_dashboard",
        "market_context": {
            "market_gate": rules.get("global_gate", {}).get("default_market_gate", "verify_only"),
            "target_equity_range": f"{fmt(allocation_map.get('target_equity_pct'), 1)}%" if allocation_map else "45%-50%",
            "allocation_map": allocation_map,
            "staleness": rules.get("staleness", {"status": "legacy_unknown"}),
            "action_plan": action_plan_context(action_plan or {}),
            "monitor_scope": rules.get("monitor_scope", {}),
            "quote_health": {
                "expected_count": len(expected_codes),
                "received_count": len(received_codes),
                "missing_count": len(expected_codes) - len(received_codes),
                "missing_codes": [code for code in expected_codes if code not in set(received_codes)],
                "latest_timetag": max(timetags) if timetags else None,
            },
        },
        "quotes": quotes,
    }


def build_reference_ticks(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ticks: dict[str, dict[str, Any]] = {}
    for subject in rules.get("subjects", []):
        ref = subject.get("reference_metrics", {})
        last = num(ref.get("last_reference")) or num((ref.get("valuation_visual") or {}).get("current_value")) or 0.0
        ticks[subject["code"]] = {
            "last": last,
            "pre_close": last,
            "pct_chg": 0.0,
            "qmt_timetag": "offline_reference_preview",
        }
    return ticks


def parse_qmt_timetag(value: str | None) -> datetime | None:
    if not value or value == "offline_reference_preview":
        return None
    try:
        return datetime.strptime(value, "%Y%m%d %H:%M:%S")
    except ValueError:
        return None


class QmtQuoteProvider:
    def __init__(self, qmt_site: Path) -> None:
        self.qmt_site = qmt_site
        self.xtdata = None
        self.error = ""
        self._load_xtdata()

    def _load_xtdata(self) -> None:
        if not self.qmt_site.exists():
            self.error = f"QMT site-packages not found: {self.qmt_site}"
            return
        sys.path.insert(0, str(self.qmt_site))
        try:
            from xtquant import xtdata  # type: ignore

            self.xtdata = xtdata
        except Exception as exc:  # noqa: BLE001
            self.error = f"QMT import failed: {exc}"

    def fetch(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        if self.xtdata is None:
            raise RuntimeError(self.error or "QMT xtdata is not available")
        ticks = self.xtdata.get_full_tick(codes) or {}
        result: dict[str, dict[str, Any]] = {}
        for code in codes:
            tick = ticks.get(code) or {}
            if not tick:
                continue
            last = num(tick.get("lastPrice"))
            pre_close = num(tick.get("lastClose"))
            if last is None or last <= 0:
                continue
            pct_chg = (last / pre_close - 1) * 100 if pre_close else None
            result[code] = {
                "last": last,
                "pre_close": pre_close,
                "pct_chg": pct_chg,
                "qmt_timetag": tick.get("timetag", ""),
            }
        return result


class BattleMapWindow(QMainWindow):
    def __init__(self, rules_file: Path, qmt_site: Path, interval_ms: int, allow_reference_fallback: bool = False) -> None:
        super().__init__()
        self.rules_file = rules_file
        self.raw_rules = load_json(rules_file)
        self.rules = filter_rules_for_monitor_pool(self.raw_rules)
        self.action_plan = load_latest_action_plan()
        self.provider = QmtQuoteProvider(qmt_site)
        self.interval_ms = interval_ms
        self.allow_reference_fallback = allow_reference_fallback
        self.last_states: dict[str, str] = {}
        self.event_path = RUNTIME_DIR / f"intraday_events_{datetime.now():%Y-%m-%d}.jsonl"
        self.event_path.parent.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle("MyInvest 盘中作战地图")
        self.resize(1420, 900)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(self.interval_ms)
        self.refresh()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f6f8fb; }
            QFrame#card { background: #ffffff; border: 1px solid #d9e2ef; border-radius: 8px; }
            QLabel#cardTitle { color: #64748b; font-size: 12px; }
            QLabel#cardValue { color: #0f172a; font-size: 20px; font-weight: 700; }
            QFrame#subjectCard { border: 1px solid #d9e2ef; border-radius: 8px; }
            QFrame#bucketFrame { background: #ffffff; border: 1px solid #d9e2ef; border-radius: 8px; }
            QPushButton { background: #1d4ed8; color: white; border: 0; border-radius: 6px; padding: 8px 14px; font-weight: 700; }
            QComboBox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; }
            QToolButton { background: transparent; border: 0; color: #0f172a; font-weight: 700; }
            """
        )
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        self.setCentralWidget(central)

        header = QHBoxLayout()
        self.status_card = self._card("市场门禁", "-")
        self.target_card = self._card("目标权益", "-")
        self.freshness_card = self._card("规则状态", "-")
        self.source_card = self._card("数据源", "QMT实时 / 本地规则")
        self.time_card = self._card("刷新时间", "-")
        header.addWidget(self.status_card)
        header.addWidget(self.target_card)
        header.addWidget(self.freshness_card)
        header.addWidget(self.source_card)
        header.addWidget(self.time_card)
        root.addLayout(header)

        self.allocation_map = AllocationMap(self.rules.get("allocation_map"))
        root.addWidget(self.allocation_map)
        self.action_panel = ActionPlanPanel(self.action_plan)
        root.addWidget(self.action_panel)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("排序"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("风险优先", "risk")
        self.sort_combo.addItem("仓位偏离优先", "position_gap")
        self.sort_combo.addItem("触发优先", "trigger")
        self.sort_combo.addItem("分组顺序", "bucket")
        self.sort_combo.currentIndexChanged.connect(lambda _idx: self.refresh())
        controls.addWidget(self.sort_combo)
        controls.addStretch(1)
        root.addLayout(controls)

        self.collapsed_buckets: dict[str, bool] = {}
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.card_layout = QVBoxLayout(self.scroll_content)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(10)
        self.scroll.setWidget(self.scroll_content)
        root.addWidget(self.scroll, stretch=1)

        footer = QHBoxLayout()
        self.detail = QLabel("等待行情...")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color:#334155;")
        refresh_btn = QPushButton("立即刷新")
        refresh_btn.clicked.connect(self.refresh)
        footer.addWidget(self.detail, stretch=1)
        footer.addWidget(refresh_btn)
        root.addLayout(footer)

    def _card(self, title: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        value_label = QLabel(value)
        value_label.setObjectName("cardValue")
        layout.addWidget(label)
        layout.addWidget(value_label)
        return frame

    def _set_card(self, frame: QFrame, value: str, color: str | None = None) -> None:
        label = frame.findChild(QLabel, "cardValue")
        if label:
            label.setText(value)
            if color:
                label.setStyleSheet(f"color:{color}; font-size:20px; font-weight:700;")

    def build_snapshot(self, ticks: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return build_snapshot_from_rules(self.rules, ticks, self.action_plan)

    def refresh(self) -> None:
        codes = [item["code"] for item in self.rules.get("subjects", [])]
        try:
            ticks = self.provider.fetch(codes)
            snapshot = self.build_snapshot(ticks)
            report = intraday_monitor.build_report(self.rules, snapshot)
        except Exception as exc:  # noqa: BLE001
            if self.allow_reference_fallback:
                ticks = build_reference_ticks(self.rules)
                snapshot = self.build_snapshot(ticks)
                snapshot["source"] = "offline_reference_preview"
                report = intraday_monitor.build_report(self.rules, snapshot)
                report["summary"]["one_line_conclusion"] = f"离线预览：QMT不可用，使用规则参考价绘制界面；原因：{exc}"
                self.timer.stop()
                self._render(report)
                return
            QMessageBox.warning(self, "盘中监测错误", str(exc))
            self.timer.stop()
            return

        self._render(report)
        self._record_state_changes(report)

    def _render(self, report: dict[str, Any]) -> None:
        context = report.get("market_context", {})
        gate = context.get("market_gate", "unknown")
        gate_color = {"risk_reduce_only": "#b00020", "verify_only": "#9a6700", "allow_new_risk": "#0a7f2e"}.get(gate)
        self._set_card(self.status_card, GATE_LABELS.get(gate, str(gate)), gate_color)
        self._set_card(self.target_card, context.get("target_equity_range", "-"))
        stale = context.get("staleness") or report.get("staleness") or {}
        stale_status = str(stale.get("status", "legacy_unknown"))
        stale_color = {"fresh": "#0a7f2e", "stale": "#b00020", "blocked": "#b00020", "degraded": "#d97706", "legacy_unknown": "#9a6700"}.get(stale_status, "#9a6700")
        self._set_card(self.freshness_card, STALE_LABELS.get(stale_status, stale_status), stale_color)
        self.freshness_card.setToolTip(staleness_tooltip(stale))
        source_label, source_color, source_tip = self._quote_health_label(report)
        self._set_card(self.source_card, source_label, source_color)
        self.source_card.setToolTip(source_tip)
        self._set_card(self.time_card, datetime.now().strftime("%H:%M:%S"))
        if context.get("allocation_map"):
            self.allocation_map.update_allocation(context["allocation_map"])

        alerts_by_code = {item["subject"]["code"]: item for item in report.get("alerts", [])}
        near_by_code = {
            str(item.get("subject", "")).split(" ", 1)[0]: item
            for item in report.get("near_triggers", [])
        }
        quotes = report.get("monitored_quotes", [])
        sorted_quotes = sorted(quotes, key=lambda item: self._quote_sort_key(item, alerts_by_code, near_by_code))
        self._clear_cards()
        for bucket in BUCKET_ORDER:
            bucket_quotes = [
                quote for quote in sorted_quotes
                if (quote.get("allocation_bucket") or subject_bucket(self._subject_by_code(quote["code"]))) == bucket
            ]
            if not bucket_quotes:
                continue
            frame = self._bucket_frame(bucket, bucket_quotes, alerts_by_code, near_by_code, context.get("allocation_map", {}), context.get("action_plan", {}))
            self.card_layout.addWidget(frame)
        self.card_layout.addStretch(1)

        summary = report.get("summary", {})
        action_summary = ((context.get("action_plan") or {}).get("summary") or {}).get("one_line_conclusion")
        monitor_scope = context.get("monitor_scope") or {}
        source_subject_count = monitor_scope.get("source_subject_count")
        active_subject_count = monitor_scope.get("active_subject_count")
        hidden_count = len(monitor_scope.get("hidden_subjects") or [])
        monitor_line = (
            f"监控 {active_subject_count}/{source_subject_count}，隐藏清仓/非观察 {hidden_count} 项。"
            if source_subject_count is not None and active_subject_count is not None
            else ""
        )
        state_text = SUMMARY_STATE_LABELS.get(str(summary.get("alert_state")), str(summary.get("alert_state") or "-"))
        priority_text = PRIORITY_LABELS.get(str(summary.get("highest_priority")), str(summary.get("highest_priority") or "-"))
        valuation_check = report.get("valuation_update_check") or {}
        valuation_count = int(valuation_check.get("update_required_count") or 0)
        valuation_line = f"估值复核 {valuation_count} 项；" if valuation_count else "估值区间未跨档；"
        self.detail.setText(
            "状态：{state}；规则={stale_status}；最高优先级：{priority}；{valuation_line}{line}。{monitor_line}今日建议：{action_line}。规则过期或降级时禁止买入/加仓，仅供观察和风险复核。".format(
                state=state_text,
                stale_status=STALE_LABELS.get(stale_status, stale_status),
                priority=priority_text,
                valuation_line=valuation_line,
                line=summary.get("one_line_conclusion"),
                monitor_line=monitor_line,
                action_line=display_ui_text(action_summary) if action_summary else "未载入",
            )
        )

    def _quote_health_label(self, report: dict[str, Any]) -> tuple[str, str, str]:
        source = report.get("quote_source", "unknown")
        context = report.get("market_context", {})
        health = context.get("quote_health", {}) or {}
        expected = int(health.get("expected_count") or 0)
        received = int(health.get("received_count") or 0)
        missing = int(health.get("missing_count") or max(expected - received, 0))
        missing_codes = health.get("missing_codes") or []
        latest = health.get("latest_timetag")

        if source == "offline_reference_preview":
            return (
                "离线预览",
                "#9a6700",
                "QMT 不可用或未连接时使用规则参考价绘图；只用于界面检查，不作为实时行情或交易触发依据。",
            )

        if received <= 0:
            return (
                "行情为空",
                "#b00020",
                "QMT 未返回有效价格。请确认 QMT 已登录、启动时已勾选“独立交易”，并且行情页能正常刷新。",
            )

        missing_text = "、".join(str(code) for code in missing_codes[:8])
        if missing > 0:
            suffix = f"；缺失：{missing_text}" if missing_text else ""
            return (
                f"部分缺失 {received}/{expected}",
                "#d97706",
                f"QMT 已返回部分标的，但仍有 {missing} 个标的缺少有效价格{suffix}。",
            )

        latest_dt = parse_qmt_timetag(str(latest) if latest else None)
        if latest_dt:
            delay_seconds = max(0, int((datetime.now() - latest_dt).total_seconds()))
            if delay_seconds > 180:
                return (
                    f"行情延迟 {delay_seconds}s",
                    "#d97706",
                    f"最新 QMT 行情时间：{latest}；超过 180 秒未更新，盘中触发需要人工复核。",
                )
            return (
                f"实时正常 {received}/{expected}",
                "#0a7f2e",
                f"QMT 实时行情正常；最新行情时间：{latest}。",
            )

        return (
            f"实时正常 {received}/{expected}",
            "#0a7f2e",
            "QMT 已返回有效价格，但没有可解析的行情时间字段。",
        )

    def _clear_cards(self) -> None:
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _quote_sort_key(self, quote: dict[str, Any], alerts_by_code: dict[str, dict[str, Any]], near_by_code: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
        code = quote["code"]
        bucket = quote.get("allocation_bucket") or subject_bucket(self._subject_by_code(code))
        bucket_rank = BUCKET_ORDER.index(bucket) if bucket in BUCKET_ORDER else len(BUCKET_ORDER)
        alert = alerts_by_code.get(code)
        near = 1 if code in near_by_code else 0
        priority = PRIORITY_RANK.get(alert.get("priority") if alert else "", 0)
        gap = abs(self._position_gap(quote.get("position_visual") or {}))
        mode = self.sort_combo.currentData()
        if mode == "position_gap":
            return (-gap, -priority, bucket_rank, code)
        if mode == "trigger":
            return (0 if alert else (1 if near else 2), -priority, bucket_rank, code)
        if mode == "bucket":
            return (bucket_rank, code)
        return (-priority, 0 if alert else (1 if near else 2), -gap, bucket_rank, code)

    def _position_gap(self, position: dict[str, Any]) -> float:
        current = num(position.get("current_position_pct")) or 0.0
        rng = parse_pct_range(position.get("target_position_range"))
        if not rng:
            return 0.0
        low, high = rng
        if low <= current <= high:
            return 0.0
        return current - high if current > high else current - low

    def _bucket_frame(
        self,
        bucket: str,
        quotes: list[dict[str, Any]],
        alerts_by_code: dict[str, dict[str, Any]],
        near_by_code: dict[str, dict[str, Any]],
        allocation_map: dict[str, Any],
        action_context: dict[str, Any],
    ) -> QFrame:
        style = BUCKET_STYLE.get(bucket, BUCKET_STYLE["legacy_watch"])
        frame = QFrame()
        frame.setObjectName("bucketFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        bucket_info = next((item for item in allocation_map.get("buckets", []) if item.get("key") == bucket), {})
        bucket_actions = (action_context.get("bucket_actions") or {}).get(bucket, [])
        alerts = sum(1 for quote in quotes if quote["code"] in alerts_by_code)
        near = sum(1 for quote in quotes if quote["code"] in near_by_code)
        hot = alerts * 2 + near + abs(num(bucket_info.get("gap_pct")) or 0) / 5
        hot_color = "#fee2e2" if hot >= 4 else ("#fef3c7" if hot >= 2 else "#e8f7f1")

        header = QHBoxLayout()
        toggle = QToolButton()
        collapsed = self.collapsed_buckets.get(bucket, False)
        toggle.setText(("▶ " if collapsed else "▼ ") + style["label"])
        toggle.clicked.connect(lambda _checked=False, key=bucket: self._toggle_bucket(key))
        action_hint = ""
        if bucket_actions:
            first = bucket_actions[0]
            action_hint = f"；建议 {display_action_type(first.get('action_type'))} {display_action_text(first.get('suggested_change'))}"
        summary = QLabel(
            "目标 {target}%，实际 {actual}%，偏离 {gap:+.2f}pp；标的 {count}，触发 {alerts}，接近 {near}".format(
                target=fmt(bucket_info.get("target_pct")),
                actual=fmt(bucket_info.get("actual_pct")),
                gap=num(bucket_info.get("gap_pct")) or 0.0,
                count=len(quotes),
                alerts=alerts,
                near=near,
            ) + action_hint
        )
        summary.setStyleSheet(f"background:{hot_color}; color:#334155; padding:5px 8px; border-radius:6px;")
        tips = ["分组热力由触发数量、接近触发和实际仓位偏离共同决定。"]
        for action in bucket_actions:
            tips.append(
                f"{display_action_type(action.get('action_type'))} {display_ui_text(action.get('subject'))}："
                f"{display_action_text(action.get('suggested_change'))}，目标 {action.get('target_position')}"
            )
        summary.setToolTip("\n".join(tips))
        header.addWidget(toggle)
        header.addWidget(summary, stretch=1)
        layout.addLayout(header)

        if not collapsed:
            for quote in quotes:
                layout.addWidget(self._subject_card(quote, alerts_by_code.get(quote["code"]), near_by_code.get(quote["code"])))
        return frame

    def _toggle_bucket(self, bucket: str) -> None:
        self.collapsed_buckets[bucket] = not self.collapsed_buckets.get(bucket, False)
        self.refresh()

    def _subject_card(self, quote: dict[str, Any], alert: dict[str, Any] | None, near: dict[str, Any] | None) -> QFrame:
        subject = self._subject_by_code(quote["code"])
        bucket = quote.get("allocation_bucket") or subject_bucket(subject)
        style = BUCKET_STYLE.get(bucket, BUCKET_STYLE["legacy_watch"])
        bg = "#fee2e2" if alert and alert.get("priority") == "high" else style["bg"]
        card = QFrame()
        card.setObjectName("subjectCard")
        card.setStyleSheet(f"QFrame#subjectCard {{ background:{bg}; border-left: 5px solid {style['accent']}; }}")
        card.setMinimumHeight(146)
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        title = QLabel(f"{quote['code']}  {quote['name']}")
        title.setStyleSheet("font-size:14px; font-weight:700; color:#0f172a;")
        price = QLabel(f"现价 {fmt(quote.get('last'), 3)}")
        price.setStyleSheet("font-size:12px; color:#334155;")
        tag_badge = self._attribute_badge(subject, quote)
        realtime_stance = self._realtime_zone_badge(quote)
        report_stance = self._report_zone_badge(quote)
        status = self._status_badge(alert, near)
        grid.addWidget(title, 0, 0)
        grid.addWidget(price, 1, 0)
        grid.addWidget(tag_badge, 2, 0)
        grid.addWidget(realtime_stance, 3, 0)
        grid.addWidget(report_stance, 4, 0)
        grid.addWidget(status, 5, 0)

        visual = quote.get("valuation_visual") or {}
        markers = quote.get("risk_markers") or {}
        position = quote.get("position_visual") or {}
        grid.addWidget(ValuationMapBar(visual, markers, quote.get("last"), bg, card), 0, 1, 6, 2)
        grid.addWidget(MoveMap(quote.get("trend_visual"), bg, card), 0, 3, 6, 2)
        grid.addWidget(PositionGapBar(position.get("current_position_pct"), position.get("target_position_range"), bg, card), 0, 5, 6, 1)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(4, 2)
        grid.setColumnStretch(5, 1)
        return card

    def _attribute_badge(self, subject: dict[str, Any], quote: dict[str, Any]) -> QLabel:
        tags = subject_attribute_tags(subject, quote)
        text = " / ".join(tags) if tags else "属性待补"
        bucket = quote.get("allocation_bucket") or subject_bucket(subject)
        bucket_label = BUCKET_STYLE.get(bucket, BUCKET_STYLE["legacy_watch"])["label"]
        widget = QLabel(text)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setWordWrap(True)
        widget.setStyleSheet(
            "background:#f8fafc; color:#334155; border:1px solid #cbd5e1; "
            "border-radius:6px; padding:3px 5px; font-size:11px; font-weight:700;"
        )
        widget.setToolTip(
            "\n".join(
                [
                    f"标的属性：{text}",
                    f"仓位桶：{bucket_label}",
                    "属性标签来自规则中的分组、角色和估值状态，用来解释标的性质；仓位桶仍用于组合层目标仓位计算。",
                ]
            )
        )
        return widget

    def _zone_color(self, label: str | None) -> str:
        text = label or ""
        if "低估" in text:
            return STANCE_COLOR.get("低估", "#16a34a")
        if "价格低位" in text:
            return STANCE_COLOR.get("价格低位", "#16a34a")
        if "合理" in text:
            return STANCE_COLOR.get("合理", "#475569")
        if "价格合理" in text:
            return STANCE_COLOR.get("价格合理", "#475569")
        if "偏贵" in text:
            return STANCE_COLOR.get("偏贵", "#d97706")
        if "价格偏贵" in text:
            return STANCE_COLOR.get("价格偏贵", "#d97706")
        if "拥挤" in text or "风险" in text or "泡沫" in text:
            return STANCE_COLOR.get("泡沫", "#b91c1c")
        return "#64748b"

    def _realtime_zone_badge(self, quote: dict[str, Any]) -> QLabel:
        zone = quote.get("realtime_valuation_zone") or {}
        label = zone.get("label") or "待判定"
        changed = bool(quote.get("valuation_zone_changed"))
        color = "#b91c1c" if changed else self._zone_color(label)
        semantic_scope = (quote.get("valuation_visual") or {}).get("semantic_scope")
        prefix = "实时价格位置" if semantic_scope == "price_position_only" else "实时区间"
        widget = QLabel(f"{prefix}：{label}")
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setStyleSheet(f"background:{color}; color:#ffffff; border-radius:6px; padding:4px 6px; font-weight:700;")
        report = quote.get("valuation_report_zone") or {}
        series = (quote.get("valuation_visual") or {}).get("price_series") or {}
        basis_line = (
            f"历史比较口径：{series.get('basis_label') or series.get('basis') or '-'}；价格带已折算到场内价格尺度。"
            if series
            else "历史比较口径：未标注。"
        )
        widget.setToolTip(
            "\n".join(
                [
                    f"实时价格：{fmt(quote.get('last'), 4)}",
                    f"实时所在区间：{label}",
                    f"报告基准区间：{report.get('label') or '-'}，基准价 {fmt(report.get('value'), 4)}，基准日 {report.get('price_date') or '-'}",
                    basis_line,
                    "实时区间由 QMT 当前价落入既有价格/估值带计算，不代表盘中重算估值报告。",
                    "实时区间与报告基准不一致，盘后应刷新估值规则。" if changed else "实时区间与报告基准一致。",
                ]
            )
        )
        return widget

    def _report_zone_badge(self, quote: dict[str, Any]) -> QLabel:
        report = quote.get("valuation_report_zone") or {}
        stance = quote.get("security_stance") or {}
        label = report.get("label") or stance.get("label") or "缺报告"
        changed = bool(quote.get("valuation_zone_changed"))
        color = "#d97706" if changed else self._zone_color(label)
        widget = QLabel(f"报告基准：{label}")
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setStyleSheet(f"background:{color}; color:#ffffff; border-radius:6px; padding:4px 6px; font-weight:700;")
        widget.setToolTip(
            "\n".join(
                [
                    f"估值报告：{report.get('source_profile') or '-'}",
                    f"报告基准日：{report.get('price_date') or '-'}",
                    f"报告基准价：{fmt(report.get('value'), 4)}",
                    stance.get("basis", "缺少标的级估值状态，上游ETF/个股研究模块需要补齐。"),
                    stance.get("boundary", "估值状态不等于组合级买卖动作。"),
                    "该报告基准已被实时价格跨区，盘后分析需提示是否更新估值报告。" if changed else "",
                ]
            ).strip()
        )
        return widget

    def _status_badge(self, alert: dict[str, Any] | None, near: dict[str, Any] | None) -> QLabel:
        if alert:
            priority = PRIORITY_LABELS.get(str(alert.get("priority")), str(alert.get("priority") or "-"))
            alert_type = ALERT_TYPE_LABELS.get(str(alert.get("alert_type")), str(alert.get("alert_type") or "-"))
            text = f"{priority} / {alert_type}"
            color = "#b91c1c" if alert.get("priority") == "high" else "#b45309"
            tooltip = "\n".join([alert.get("trigger_condition", ""), alert.get("execution_boundary", "")])
        elif near:
            text = "接近触发"
            color = "#d97706"
            tooltip = near.get("watch_point", "")
        else:
            text = "未触发"
            color = "#475569"
            tooltip = "未触发已定义盘中规则。"
        widget = QLabel(text)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setStyleSheet(f"background:{color}; color:#ffffff; border-radius:6px; padding:4px 6px; font-weight:700;")
        widget.setToolTip(tooltip)
        return widget

    def _subject_by_code(self, code: str) -> dict[str, Any]:
        for subject in self.rules.get("subjects", []):
            if subject.get("code") == code:
                return subject
        return {}

    def _record_state_changes(self, report: dict[str, Any]) -> None:
        current_states: dict[str, str] = {}
        for alert in report.get("alerts", []):
            subject = alert["subject"]
            key = f"{subject['code']}:{alert['alert_type']}:{alert['trigger_condition']}"
            current_states[key] = alert["current_state"]
            if self.last_states.get(key) != alert["current_state"]:
                event = {
                    "time": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                    "code": subject["code"],
                    "name": subject["name"],
                    "alert_type": alert["alert_type"],
                    "priority": alert["priority"],
                    "condition": alert["trigger_condition"],
                    "action": alert["suggested_action"],
                }
                self.event_path.open("a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\n")
        self.last_states = current_states


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-file", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--qmt-site", type=Path, default=DEFAULT_QMT_SITE)
    parser.add_argument("--interval-ms", type=int, default=3000)
    parser.add_argument("--once-json", action="store_true", help="Fetch QMT once, print evaluated JSON, and exit.")
    parser.add_argument("--preview-png", type=Path, help="Open once, save a dashboard preview PNG, and exit.")
    parser.add_argument("--reference-fallback", action="store_true", help="Use rule reference prices when QMT is offline. Only for offline checks and screenshots.")
    args = parser.parse_args(argv)

    if args.once_json:
        rules = filter_rules_for_monitor_pool(load_json(args.rules_file))
        provider = QmtQuoteProvider(args.qmt_site)
        codes = [item["code"] for item in rules.get("subjects", [])]
        try:
            ticks = provider.fetch(codes)
        except Exception:
            if not args.reference_fallback:
                raise
            ticks = build_reference_ticks(rules)
        action_plan = load_latest_action_plan()
        snapshot = build_snapshot_from_rules(rules, ticks, action_plan)
        if args.reference_fallback and all(item.get("qmt_timetag") == "offline_reference_preview" for item in ticks.values()):
            snapshot["source"] = "offline_reference_preview"
        report = intraday_monitor.build_report(rules, snapshot)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    app = QApplication(sys.argv)
    tooltip_filter = LongToolTipFilter(app)
    app.installEventFilter(tooltip_filter)
    window = BattleMapWindow(args.rules_file, args.qmt_site, args.interval_ms, allow_reference_fallback=bool(args.preview_png or args.reference_fallback))
    window.show()
    if args.preview_png:
        def save_preview() -> None:
            args.preview_png.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(args.preview_png))
            app.quit()

        QTimer.singleShot(800, save_preview)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
