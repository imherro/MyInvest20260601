#!/usr/bin/env python3
"""Realtime intraday battle map using QMT quotes and fixed local rules."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def parse_range_center(text: str | None) -> str:
    if not text:
        return "-"
    return text


def valuation_zone_for_value(visual: dict[str, Any], value: Any) -> dict[str, Any] | None:
    try:
        current = float(value)
    except (TypeError, ValueError):
        return None
    for zone in visual.get("zones", []):
        if float(zone["min"]) <= current <= float(zone["max"]):
            return zone
    zones = visual.get("zones", [])
    if not zones:
        return None
    if current < float(zones[0]["min"]):
        return zones[0]
    return zones[-1]


class ValuationBar(QWidget):
    def __init__(self, visual: dict[str, Any], current_value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.visual = visual
        self.current_value = current_value
        self.setMinimumHeight(34)
        self.setToolTip(self.tooltip_text())

    def tooltip_text(self) -> str:
        zone = valuation_zone_for_value(self.visual, self.current_value)
        label = zone.get("label", "-") if zone else "-"
        parts = [f"当前位置：{label}", f"当前值：{fmt(self.current_value, 4)}"]
        for item in self.visual.get("zones", []):
            parts.append(f"{item['label']}：{fmt(item['min'], 4)}-{fmt(item['max'], 4)}")
        return "\n".join(parts)

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt override.
        zones = self.visual.get("zones", [])
        if not zones:
            return
        minimum = float(zones[0]["min"])
        maximum = float(zones[-1]["max"])
        if maximum <= minimum:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(6, 8, -6, -10)
        span = maximum - minimum

        for zone in zones:
            left_ratio = (float(zone["min"]) - minimum) / span
            right_ratio = (float(zone["max"]) - minimum) / span
            x = rect.left() + rect.width() * left_ratio
            w = max(2, rect.width() * (right_ratio - left_ratio))
            painter.fillRect(int(x), rect.top(), int(w), rect.height(), QColor(zone.get("color", "#cccccc")))

        painter.setPen(QPen(QColor("#333333"), 1))
        painter.drawRect(rect)

        try:
            current = float(self.current_value)
        except (TypeError, ValueError):
            current = minimum
        marker_ratio = min(1.0, max(0.0, (current - minimum) / span))
        marker_x = rect.left() + rect.width() * marker_ratio
        painter.setPen(QPen(QColor("#111111"), 3))
        painter.drawLine(int(marker_x), rect.top() - 4, int(marker_x), rect.bottom() + 4)
        painter.setPen(QPen(QColor("#111111"), 1))
        painter.drawText(rect.left(), self.height() - 2, fmt(current, 3))


def build_snapshot_from_rules(rules: dict[str, Any], ticks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    quotes: dict[str, dict[str, Any]] = {}
    for subject in rules.get("subjects", []):
        code = subject["code"]
        ref = subject.get("reference_metrics", {})
        live = ticks.get(code, {})
        quote = {
            "name": subject.get("name", code),
            "type": subject.get("type", "unknown"),
            "last": live.get("last"),
            "pre_close": live.get("pre_close"),
            "pct_chg": live.get("pct_chg"),
            "amount_100m": live.get("amount_100m"),
            "turnover_rate": ref.get("turnover_rate"),
            "volume_ratio": ref.get("volume_ratio"),
            "ma20": ref.get("ma20"),
            "ma60": ref.get("ma60"),
            "moneyflow_5d": ref.get("moneyflow_5d"),
            "moneyflow_20d": ref.get("moneyflow_20d"),
            "rel_hs300_intraday_pct": live.get("rel_hs300_intraday_pct"),
            "qmt_timetag": live.get("qmt_timetag"),
            "valuation_visual": ref.get("valuation_visual"),
        }
        quotes[code] = quote
    return {
        "module": "intraday_quotes_snapshot",
        "version": "1.0",
        "timestamp": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "source": "qmt_dashboard",
        "market_context": {
            "market_gate": rules.get("global_gate", {}).get("default_market_gate", "verify_only"),
            "target_equity_range": "45%-50%",
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
        except Exception as exc:  # noqa: BLE001 - show user local QMT issue.
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
                "amount_100m": float(tick.get("amount") or 0) / 100000000,
                "qmt_timetag": tick.get("timetag", ""),
                "bid1": (tick.get("bidPrice") or [None])[0],
                "ask1": (tick.get("askPrice") or [None])[0],
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
        self.resize(1280, 820)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(self.interval_ms)
        self.refresh()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
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

        self.table = QTableWidget(0, 15)
        self.table.setHorizontalHeaderLabels(
            [
                "标的",
                "分组",
                "当前价",
                "估值分段",
                "涨跌幅",
                "成交额(亿)",
                "MA20",
                "MA60",
                "距MA60",
                "风控位",
                "右侧确认",
                "当前仓位",
                "理想仓位",
                "状态",
                "行情时间",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 210)
        self.table.setColumnWidth(3, 260)
        root.addWidget(self.table, stretch=3)

        lower = QGridLayout()
        self.detail = QLabel("等待行情...")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail.setWordWrap(True)
        self.detail.setFrameShape(QFrame.Shape.StyledPanel)
        self.events = QLabel("事件流")
        self.events.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.events.setWordWrap(True)
        self.events.setFrameShape(QFrame.Shape.StyledPanel)
        lower.addWidget(self.detail, 0, 0)
        lower.addWidget(self.events, 0, 1)
        root.addLayout(lower, stretch=1)

        buttons = QHBoxLayout()
        refresh_btn = QPushButton("立即刷新")
        refresh_btn.clicked.connect(self.refresh)
        buttons.addWidget(refresh_btn)
        buttons.addStretch()
        root.addLayout(buttons)

    def _card(self, title: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        label = QLabel(title)
        label.setStyleSheet("color: #666; font-size: 12px;")
        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(label)
        layout.addWidget(value_label)
        return frame

    def _set_card(self, frame: QFrame, value: str, color: str | None = None) -> None:
        label = frame.findChild(QLabel, "value")
        if label:
            style = "font-size: 20px; font-weight: 600;"
            if color:
                style += f" color: {color};"
            label.setText(value)
            label.setStyleSheet(style)

    def build_snapshot(self, ticks: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return build_snapshot_from_rules(self.rules, ticks)

    def refresh(self) -> None:
        codes = [item["code"] for item in self.rules.get("subjects", [])]
        try:
            ticks = self.provider.fetch(codes)
            snapshot = self.build_snapshot(ticks)
            report = intraday_monitor.build_report(self.rules, snapshot)
        except Exception as exc:  # noqa: BLE001 - show local runtime issue.
            QMessageBox.warning(self, "盘中监测错误", str(exc))
            self.timer.stop()
            return

        self._render(report)
        self._record_state_changes(report)

    def _render(self, report: dict[str, Any]) -> None:
        gate = report.get("market_context", {}).get("market_gate", "unknown")
        gate_color = {"risk_reduce_only": "#b00020", "verify_only": "#9a6700", "allow_new_risk": "#0a7f2e"}.get(gate)
        self._set_card(self.status_card, gate, gate_color)
        self._set_card(self.target_card, report.get("market_context", {}).get("target_equity_range", "-"))
        self._set_card(self.time_card, datetime.now().strftime("%H:%M:%S"))

        quotes = report.get("monitored_quotes", [])
        alerts_by_code = {item["subject"]["code"]: item for item in report.get("alerts", [])}
        near_subjects = {item["subject"].split()[0]: item for item in report.get("near_triggers", [])}

        self.table.setRowCount(len(quotes))
        for row, quote in enumerate(quotes):
            subject = self._subject_by_code(quote["code"])
            ref = subject.get("reference_metrics", {})
            alert = alerts_by_code.get(quote["code"])
            near = near_subjects.get(quote["code"])
            status = "未触发"
            color = QColor("#f4f7fb")
            if alert:
                status = f"{alert['priority']} / {alert['alert_type']}"
                color = QColor("#ffd6d6") if alert["priority"] == "high" else QColor("#fff0c2")
            elif near:
                status = "接近触发"
                color = QColor("#fff6d5")

            ma60 = quote.get("ma60")
            last = quote.get("last")
            dist60 = (float(last) / float(ma60) - 1) * 100 if last and ma60 else None
            visual = ref.get("valuation_visual")
            zone = valuation_zone_for_value(visual, last) if isinstance(visual, dict) else None
            zone_label = zone.get("label", "-") if zone else "-"
            values = [
                f"{quote['code']} {quote['name']}",
                subject.get("group", "-"),
                fmt(last),
                zone_label,
                fmt(quote.get("pct_chg")),
                fmt(quote.get("amount_100m")),
                fmt(quote.get("ma20")),
                fmt(ma60),
                fmt(dist60),
                fmt(ref.get("support")),
                fmt(ref.get("right_confirm")),
                fmt(ref.get("current_position_pct")),
                parse_range_center(ref.get("target_position_range")),
                status,
                str(quote.get("qmt_timetag") or "-"),
            ]
            for col, value in enumerate(values):
                if col == 3 and isinstance(visual, dict):
                    self.table.setCellWidget(row, col, ValuationBar(visual, last, self.table))
                    continue
                item = QTableWidgetItem(value)
                item.setBackground(color)
                if col in {2, 4, 5, 6, 7, 8, 9, 10, 11}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 42)

        summary = report.get("summary", {})
        self.detail.setText(
            "总体状态：{state}\n最高优先级：{priority}\n结论：{line}\n\n边界：提醒不是交易指令；加仓/减仓仍需 ACTION_PLAN 复核。".format(
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
        lines = []
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
                lines.append(f"{event['time']} {event['code']} {event['alert_type']} {event['condition']}")

        self.last_states = current_states
        if lines:
            existing = self.events.text()
            self.events.setText("\n".join(lines + [existing])[:4000])


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
