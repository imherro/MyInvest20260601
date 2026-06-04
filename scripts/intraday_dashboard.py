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
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
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
        self.setMinimumHeight(54)
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
        self.setMinimumHeight(54)
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
            rect = QRectF(8 + idx * width, 13, width - 6, 28)
            painter.setBrush(QColor(item.get("color", "#94a3b8")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 7, 7)
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            text = f"{labels.get(item.get('key'), item.get('label', '-')[:1])} {item.get('state', '-')}"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class MoveMap(QWidget):
    def __init__(self, trend_visual: dict[str, Any] | None, bg_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.trend_visual = trend_visual or {}
        self.bg_color = bg_color
        self.setMinimumHeight(54)
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
                f"常见120日回撤：{fmt(dd.get('common_120d_drawdown_pct'))}%，深度回撤参考：{fmt(dd.get('deep_120d_drawdown_pct'))}%",
                f"前低：{fmt(rb.get('sample_low'), 4)}（{rb.get('sample_low_date') or '-'}）",
                f"从前低至今涨幅：{fmt(rb.get('from_sample_low_pct'))}%",
                f"常见120日反弹：{fmt(rb.get('common_120d_rebound_pct'))}%，强反弹参考：{fmt(rb.get('strong_120d_rebound_pct'))}%",
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
        deep_dd = abs(num(dd.get("deep_120d_drawdown_pct")) or common_dd or drawdown or 1)
        rebound = num(rb.get("from_sample_low_pct")) or 0
        common_rb = num(rb.get("common_120d_rebound_pct")) or 0
        strong_rb = num(rb.get("strong_120d_rebound_pct")) or common_rb or rebound or 1

        left = 64
        width = self.width() - 82
        rows = [("回撤", drawdown, common_dd, max(deep_dd * 1.25, drawdown, 1), "#dc2626"), ("反弹", rebound, common_rb, max(strong_rb * 1.15, rebound, 1), "#16a34a")]
        painter.setFont(QFont("Microsoft YaHei", 8))
        for idx, (label, value, common, scale, color) in enumerate(rows):
            y = 10 + idx * 22
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawText(QRectF(8, y - 2, 48, 16), Qt.AlignmentFlag.AlignRight, label)
            base = QRectF(left, y, width, 10)
            painter.setBrush(QColor("#d7dee8"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(base, 5, 5)
            fill_width = min(width, width * value / scale)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(left, y, fill_width, 10), 5, 5)
            marker_x = left + min(width, width * common / scale)
            painter.setPen(QPen(QColor("#0f172a"), 2))
            painter.drawLine(int(marker_x), y - 3, int(marker_x), y + 13)
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawText(QRectF(left + width - 56, y - 5, 56, 18), Qt.AlignmentFlag.AlignRight, f"{value:.1f}%")


class PositionGapBar(QWidget):
    def __init__(self, current_pct: Any, target_range: str | None, bg_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_pct = num(current_pct) or 0.0
        self.target_range = target_range
        self.bg_color = bg_color
        self.setMinimumHeight(54)
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
        self.setMinimumHeight(150)
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

        target_equity = num(self.allocation.get("target_equity_pct")) or 0
        actual_equity = num(self.allocation.get("actual_equity_pct")) or 0
        x, y, width = 18, 36, self.width() - 36
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(x, y, 120, 18), Qt.AlignmentFlag.AlignLeft, "总权益")
        bar = QRectF(x + 72, y + 3, width - 170, 12)
        painter.setBrush(QColor("#334155"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bar, 6, 6)
        painter.setBrush(QColor("#60a5fa"))
        painter.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * target_equity / 100, bar.height()), 6, 6)
        painter.setPen(QPen(QColor("#f8fafc"), 3))
        actual_x = bar.left() + bar.width() * min(1, actual_equity / 100)
        painter.drawLine(int(actual_x), int(bar.top() - 5), int(actual_x), int(bar.bottom() + 5))
        painter.setPen(QColor("#e5eefb"))
        painter.drawText(QRectF(bar.right() + 8, y - 1, 88, 18), Qt.AlignmentFlag.AlignLeft, f"{actual_equity:.1f}/{target_equity:.1f}%")

        buckets = self.allocation.get("buckets", [])
        bucket_y = 68
        row_h = 16
        for idx, item in enumerate(buckets[:5]):
            yy = bucket_y + idx * row_h
            label = item.get("label", "-")
            color = QColor(item.get("color", "#94a3b8"))
            target = num(item.get("target_pct")) or 0
            actual = num(item.get("actual_pct")) or 0
            painter.setPen(QColor("#dbeafe"))
            painter.drawText(QRectF(x, yy - 2, 116, 16), Qt.AlignmentFlag.AlignRight, label)
            small = QRectF(x + 126, yy, width - 230, 9)
            painter.setBrush(QColor("#263447"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(small, 5, 5)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(small.left(), small.top(), small.width() * min(1.0, target / 60), small.height()), 5, 5)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            ax = small.left() + small.width() * min(1.0, actual / 60)
            painter.drawLine(int(ax), int(small.top() - 3), int(ax), int(small.bottom() + 3))
            gap = actual - target
            gap_color = "#ef4444" if gap > 1 else ("#22c55e" if gap < -1 else "#cbd5e1")
            painter.setPen(QColor(gap_color))
            painter.drawText(QRectF(small.right() + 8, yy - 4, 92, 18), Qt.AlignmentFlag.AlignLeft, f"{actual:.1f}/{target:.1f}%")


def build_snapshot_from_rules(rules: dict[str, Any], ticks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    quotes: dict[str, dict[str, Any]] = {}
    for subject in rules.get("subjects", []):
        code = subject["code"]
        ref = subject.get("reference_metrics", {})
        live = ticks.get(code, {})
        last = live.get("last")
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
        },
        "quotes": quotes,
    }


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
            last = float(tick.get("lastPrice") or 0)
            pre_close = float(tick.get("lastClose") or 0)
            pct_chg = (last / pre_close - 1) * 100 if pre_close else None
            result[code] = {
                "last": last,
                "pre_close": pre_close,
                "pct_chg": pct_chg,
                "qmt_timetag": tick.get("timetag", ""),
            }
        return result


class BattleMapWindow(QMainWindow):
    def __init__(self, rules_file: Path, qmt_site: Path, interval_ms: int) -> None:
        super().__init__()
        self.rules_file = rules_file
        self.rules = load_json(rules_file)
        self.provider = QmtQuoteProvider(qmt_site)
        self.interval_ms = interval_ms
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
            QTableWidget { background: #ffffff; gridline-color: #d9e2ef; selection-background-color: #dbeafe; border: 1px solid #d9e2ef; }
            QHeaderView::section { background: #162033; color: #e5eefb; border: 0; padding: 8px; font-weight: 700; }
            QPushButton { background: #1d4ed8; color: white; border: 0; border-radius: 6px; padding: 8px 14px; font-weight: 700; }
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

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["标的", "仓位类型", "估值作战带", "长/中/短趋势", "前高回撤 / 前低反弹", "仓位差距", "状态"])
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        root.addWidget(self.table, stretch=1)

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
        self._set_card(self.time_card, datetime.now().strftime("%H:%M:%S"))
        if context.get("allocation_map"):
            self.allocation_map.update_allocation(context["allocation_map"])

        alerts_by_code = {item["subject"]["code"]: item for item in report.get("alerts", [])}
        quotes = report.get("monitored_quotes", [])
        self.table.setRowCount(len(quotes))
        for row, quote in enumerate(quotes):
            subject = self._subject_by_code(quote["code"])
            bucket = quote.get("allocation_bucket") or subject_bucket(subject)
            style = BUCKET_STYLE.get(bucket, BUCKET_STYLE["legacy_watch"])
            bg = style["bg"]
            alert = alerts_by_code.get(quote["code"])
            if alert:
                status = f"{alert['priority']} / {alert['alert_type']}"
                status_color = "#fee2e2" if alert["priority"] == "high" else "#fef3c7"
            else:
                status = "未触发"
                status_color = bg

            visual = quote.get("valuation_visual") or {}
            markers = quote.get("risk_markers") or {}
            position = quote.get("position_visual") or {}
            cells = [
                f"{quote['code']}\n{quote['name']}\n现价 {fmt(quote.get('last'), 3)}",
                style["label"],
                "",
                "",
                "",
                "",
                status,
            ]
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setBackground(QColor(status_color if col == 6 else bg))
                if col in {0, 1, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

            self.table.setCellWidget(row, 2, ValuationMapBar(visual, markers, quote.get("last"), bg, self.table))
            self.table.setCellWidget(row, 3, TrendStrip(quote.get("trend_visual"), bg, self.table))
            self.table.setCellWidget(row, 4, MoveMap(quote.get("trend_visual"), bg, self.table))
            self.table.setCellWidget(row, 5, PositionGapBar(position.get("current_position_pct"), position.get("target_position_range"), bg, self.table))
            self.table.setRowHeight(row, 62)

        summary = report.get("summary", {})
        self.detail.setText(
            "状态：{state}；最高优先级：{priority}；{line}。提醒只代表需要复核，最终动作仍由 ACTION_PLAN 决定。".format(
                state=summary.get("alert_state"),
                priority=summary.get("highest_priority"),
                line=summary.get("one_line_conclusion"),
            )
        )

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
    args = parser.parse_args(argv)

    if args.once_json:
        rules = load_json(args.rules_file)
        provider = QmtQuoteProvider(args.qmt_site)
        codes = [item["code"] for item in rules.get("subjects", [])]
        ticks = provider.fetch(codes)
        snapshot = build_snapshot_from_rules(rules, ticks)
        report = intraday_monitor.build_report(rules, snapshot)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    app = QApplication(sys.argv)
    window = BattleMapWindow(args.rules_file, args.qmt_site, args.interval_ms)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
