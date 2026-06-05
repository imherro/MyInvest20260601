#!/usr/bin/env python3
"""Realtime intraday battle map using QMT quotes and fixed local rules."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
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
DEFAULT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
DEFAULT_QMT_SITE = Path(r"D:\国金证券QMT交易端\python\Lib\site-packages")
RUNTIME_DIR = ROOT / "runtime" / "alerts"

BUCKET_STYLE = {
    "cash_short": {"label": "现金/短融", "bg": "#eef2f7", "accent": "#5b6b7a"},
    "core_base": {"label": "宽基/核心底仓", "bg": "#eaf2ff", "accent": "#2f6fbd"},
    "attack_mainline": {"label": "进攻主线仓", "bg": "#f2ecff", "accent": "#8b5cf6"},
    "defense": {"label": "防御仓", "bg": "#e8f7f1", "accent": "#0f8b6f"},
    "legacy_watch": {"label": "其他/待清理", "bg": "#fff4df", "accent": "#9a6700"},
}
BUCKET_ORDER = ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch"]
PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}
STANCE_COLOR = {"低估": "#16a34a", "合理": "#475569", "偏贵": "#d97706", "泡沫": "#b91c1c"}


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


def subject_bucket(subject: dict[str, Any]) -> str:
    return subject.get("allocation_bucket") or subject.get("reference_metrics", {}).get("allocation_bucket") or "legacy_watch"


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
        parts = [
            f"当前位置：{zone.get('label', '-') if zone else '-'}",
            f"当前价格/净值：{fmt(self.current_value, 4)}",
            "黑色竖线：实时当前位置",
        ]
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
        return "\n".join(
            [
                f"前高：{fmt(dd.get('sample_high'), 4)}（{dd.get('sample_high_date') or '-'}）",
                f"从前高至今回撤：{fmt(dd.get('from_sample_high_pct'))}%",
                f"常见120日回撤：{fmt(dd.get('common_120d_drawdown_pct'))}%，深度回撤参考：{fmt(dd.get('deep_120d_drawdown_pct'))}%，极值：{fmt(dd.get('max_120d_drawdown_pct'))}%",
                f"前低：{fmt(rb.get('sample_low'), 4)}（{rb.get('sample_low_date') or '-'}）",
                f"从前低至今涨幅：{fmt(rb.get('from_sample_low_pct'))}%",
                f"常见120日反弹：{fmt(rb.get('common_120d_rebound_pct'))}%，强反弹参考：{fmt(rb.get('strong_120d_rebound_pct'))}%，极值：{fmt(rb.get('max_120d_rebound_pct'))}%",
            ]
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
            ("回撤", drawdown, common_dd, deep_dd, max(max_dd, drawdown, 1), "#16a34a", True),
            ("反弹", rebound, common_rb, strong_rb, max(max_rb, rebound, 1), "#dc2626", False),
        ]
        painter.setFont(QFont("Microsoft YaHei", 8))
        gauge_w = (self.width() - 24) / 2
        for idx, (label, value, normal, strong, scale, color, down) in enumerate(gauges):
            box = QRectF(8 + idx * gauge_w, 6, gauge_w - 8, 44)
            bar = QRectF(box.left() + 16, box.top() + 4, 10, box.height() - 12)
            painter.setPen(QColor("#334155"))
            painter.drawText(QRectF(box.left(), box.top(), 36, 14), Qt.AlignmentFlag.AlignLeft, label)
            painter.setBrush(QColor("#d7dee8"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar, 5, 5)

            normal_y = self._y_for_vertical(bar, normal, scale, down)
            strong_y = self._y_for_vertical(bar, strong, scale, down)
            zone_top = min(normal_y, strong_y)
            zone_h = abs(strong_y - normal_y)
            painter.setBrush(QColor("#fde68a"))
            painter.drawRect(QRectF(bar.left(), zone_top, bar.width(), max(2, zone_h)))

            current_y = self._y_for_vertical(bar, value, scale, down)
            painter.setPen(QPen(QColor(color), 3))
            painter.drawLine(int(bar.left() - 5), int(current_y), int(bar.right() + 5), int(current_y))
            painter.setPen(QColor("#334155"))
            painter.drawText(QRectF(bar.right() + 8, box.top() + 17, box.width() - 30, 18), Qt.AlignmentFlag.AlignLeft, f"{value:.1f}%")

    def _y_for_vertical(self, rect: QRectF, value: float, scale: float, down: bool) -> float:
        ratio = min(1.0, max(0.0, value / scale if scale else 0.0))
        return rect.top() + rect.height() * ratio if down else rect.bottom() - rect.height() * ratio


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
        self.setMinimumHeight(166)
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
        painter.drawText(18, 24, "理想仓位底图")
        if not self.allocation:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "未找到最新仓位底图")
            return

        x, width = 18, self.width() - 36
        total_row = QRectF(x, 42, width, 24)
        bucket_row = QRectF(x, 92, width, 28)
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(x, 24, width, 16), Qt.AlignmentFlag.AlignLeft, "理想结构：总资产 100%，真实持仓仅作覆盖标记")

        total_segments = [
            {"label": "现金/短融", "pct": num(self.allocation.get("target_cash_short_pct")) or 0, "color": "#5b6b7a"},
            {"label": "权益", "pct": num(self.allocation.get("target_equity_pct")) or 0, "color": "#60a5fa"},
        ]
        self._draw_segments(painter, total_row, total_segments, "pct")

        ideal_segments = [
            {"label": item.get("label"), "pct": item.get("target_pct"), "color": item.get("color")}
            for item in self.allocation.get("ideal_segments", [])
            if (num(item.get("target_pct")) or 0) > 0
        ]
        self._draw_segments(painter, bucket_row, ideal_segments, "pct")

        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(x, 72, width, 16), Qt.AlignmentFlag.AlignLeft, "理想仓位桶")
        painter.drawText(QRectF(x, 126, width, 16), Qt.AlignmentFlag.AlignLeft, "真实持仓覆盖")
        self._draw_actual_overlay(painter, QRectF(x, 142, width, 10))

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
        for item in self.allocation.get("actual_overlay", []):
            actual = num(item.get("actual_pct")) or 0
            if actual <= 0:
                continue
            seg_w = rect.width() * min(actual, 100.0) / 100.0
            painter.setBrush(QColor(item.get("color", "#94a3b8")))
            painter.drawRoundedRect(QRectF(cursor, rect.top(), seg_w, rect.height()), 5, 5)
            cursor += seg_w

        cursor = rect.left()
        painter.setFont(QFont("Microsoft YaHei", 8))
        for item in self.allocation.get("actual_overlay", []):
            actual = num(item.get("actual_pct")) or 0
            if actual <= 0:
                continue
            seg_w = rect.width() * min(actual, 100.0) / 100.0
            gap = num(item.get("gap_pct")) or 0
            color = "#fecaca" if gap > 1 else ("#bbf7d0" if gap < -1 else "#e5eefb")
            painter.setPen(QColor(color))
            painter.drawText(QRectF(cursor, rect.bottom() + 2, max(64, seg_w), 16), Qt.AlignmentFlag.AlignLeft, f"{item.get('label')} {actual:.1f}%")
            cursor += seg_w


def build_snapshot_from_rules(rules: dict[str, Any], ticks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    quotes: dict[str, dict[str, Any]] = {}
    expected_codes = [item["code"] for item in rules.get("subjects", [])]
    received_codes = []
    timetags = []
    for subject in rules.get("subjects", []):
        code = subject["code"]
        ref = subject.get("reference_metrics", {})
        live = ticks.get(code, {})
        last = live.get("last")
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
            "valuation_visual": ref.get("valuation_visual"),
            "trend_visual": ref.get("trend_visual"),
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
        self.rules = load_json(rules_file)
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
        self.source_card = self._card("数据源", "QMT实时 / 本地规则")
        self.time_card = self._card("刷新时间", "-")
        header.addWidget(self.status_card)
        header.addWidget(self.target_card)
        header.addWidget(self.source_card)
        header.addWidget(self.time_card)
        root.addLayout(header)

        self.allocation_map = AllocationMap(self.rules.get("allocation_map"))
        root.addWidget(self.allocation_map)

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
        return build_snapshot_from_rules(self.rules, ticks)

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
        self._set_card(self.status_card, gate, gate_color)
        self._set_card(self.target_card, context.get("target_equity_range", "-"))
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
            frame = self._bucket_frame(bucket, bucket_quotes, alerts_by_code, near_by_code, context.get("allocation_map", {}))
            self.card_layout.addWidget(frame)
        self.card_layout.addStretch(1)

        summary = report.get("summary", {})
        self.detail.setText(
            "状态：{state}；最高优先级：{priority}；{line}。提醒只代表需要复核，最终动作仍由 ACTION_PLAN 决定。".format(
                state=summary.get("alert_state"),
                priority=summary.get("highest_priority"),
                line=summary.get("one_line_conclusion"),
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
    ) -> QFrame:
        style = BUCKET_STYLE.get(bucket, BUCKET_STYLE["legacy_watch"])
        frame = QFrame()
        frame.setObjectName("bucketFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        bucket_info = next((item for item in allocation_map.get("buckets", []) if item.get("key") == bucket), {})
        alerts = sum(1 for quote in quotes if quote["code"] in alerts_by_code)
        near = sum(1 for quote in quotes if quote["code"] in near_by_code)
        hot = alerts * 2 + near + abs(num(bucket_info.get("gap_pct")) or 0) / 5
        hot_color = "#fee2e2" if hot >= 4 else ("#fef3c7" if hot >= 2 else "#e8f7f1")

        header = QHBoxLayout()
        toggle = QToolButton()
        collapsed = self.collapsed_buckets.get(bucket, False)
        toggle.setText(("▶ " if collapsed else "▼ ") + style["label"])
        toggle.clicked.connect(lambda _checked=False, key=bucket: self._toggle_bucket(key))
        summary = QLabel(
            "目标 {target}%，实际 {actual}%，偏离 {gap:+.2f}pp；标的 {count}，触发 {alerts}，接近 {near}".format(
                target=fmt(bucket_info.get("target_pct")),
                actual=fmt(bucket_info.get("actual_pct")),
                gap=num(bucket_info.get("gap_pct")) or 0.0,
                count=len(quotes),
                alerts=alerts,
                near=near,
            )
        )
        summary.setStyleSheet(f"background:{hot_color}; color:#334155; padding:5px 8px; border-radius:6px;")
        summary.setToolTip("分组热力由触发数量、接近触发和实际仓位偏离共同决定。")
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
        card.setMinimumHeight(126)
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        title = QLabel(f"{quote['code']}  {quote['name']}")
        title.setStyleSheet("font-size:14px; font-weight:700; color:#0f172a;")
        price = QLabel(f"现价 {fmt(quote.get('last'), 3)}")
        price.setStyleSheet("font-size:12px; color:#334155;")
        stance = self._stance_badge(quote.get("security_stance"))
        status = self._status_badge(alert, near)
        grid.addWidget(title, 0, 0)
        grid.addWidget(price, 1, 0)
        grid.addWidget(stance, 2, 0)
        grid.addWidget(status, 3, 0)

        visual = quote.get("valuation_visual") or {}
        markers = quote.get("risk_markers") or {}
        position = quote.get("position_visual") or {}
        grid.addWidget(ValuationMapBar(visual, markers, quote.get("last"), bg, card), 0, 1, 4, 2)
        grid.addWidget(TrendStrip(quote.get("trend_visual"), bg, card), 0, 3, 4, 1)
        grid.addWidget(MoveMap(quote.get("trend_visual"), bg, card), 0, 4, 4, 1)
        grid.addWidget(PositionGapBar(position.get("current_position_pct"), position.get("target_position_range"), bg, card), 0, 5, 4, 1)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(4, 2)
        grid.setColumnStretch(5, 1)
        return card

    def _stance_badge(self, stance: dict[str, Any] | None) -> QLabel:
        stance = stance or {}
        label = stance.get("label", "待研究")
        color = STANCE_COLOR.get(label, "#64748b")
        widget = QLabel(f"估值状态：{label}")
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setStyleSheet(f"background:{color}; color:#ffffff; border-radius:6px; padding:4px 6px; font-weight:700;")
        widget.setToolTip(
            "\n".join(
                [
                    stance.get("basis", "缺少标的级估值状态，上游ETF/个股研究模块需要补齐。"),
                    stance.get("boundary", "估值状态不等于组合级买卖动作。"),
                ]
            )
        )
        return widget

    def _status_badge(self, alert: dict[str, Any] | None, near: dict[str, Any] | None) -> QLabel:
        if alert:
            text = f"{alert.get('priority')} / {alert.get('alert_type')}"
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-file", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--qmt-site", type=Path, default=DEFAULT_QMT_SITE)
    parser.add_argument("--interval-ms", type=int, default=3000)
    parser.add_argument("--once-json", action="store_true", help="Fetch QMT once, print evaluated JSON, and exit.")
    parser.add_argument("--preview-png", type=Path, help="Open once, save a dashboard preview PNG, and exit.")
    parser.add_argument("--reference-fallback", action="store_true", help="Use rule reference prices when QMT is offline. Only for offline checks and screenshots.")
    args = parser.parse_args(argv)

    if args.once_json:
        rules = load_json(args.rules_file)
        provider = QmtQuoteProvider(args.qmt_site)
        codes = [item["code"] for item in rules.get("subjects", [])]
        try:
            ticks = provider.fetch(codes)
        except Exception:
            if not args.reference_fallback:
                raise
            ticks = build_reference_ticks(rules)
        snapshot = build_snapshot_from_rules(rules, ticks)
        if args.reference_fallback and all(item.get("qmt_timetag") == "offline_reference_preview" for item in ticks.values()):
            snapshot["source"] = "offline_reference_preview"
        report = intraday_monitor.build_report(rules, snapshot)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    app = QApplication(sys.argv)
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
