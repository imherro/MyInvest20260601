from __future__ import annotations

from copy import deepcopy


ROLE_WORKBENCHES: dict[str, dict[str, object]] = {
    "manager": {
        "role": "manager",
        "title": "基金经理工作台",
        "subtitle": "市场判断、目标仓位与组合结构入口。",
        "tool_group": "基金经理",
        "metrics": [
            {"label": "职责", "value": "市场与仓位"},
            {"label": "边界", "value": "ratio-only"},
            {"label": "模式", "value": "current-only"},
            {"label": "交易", "value": "off", "tone": "warn"},
        ],
        "workflows": [
            {
                "title": "市场到仓位",
                "steps": ["市场历史", "理想仓位", "仓位框架", "历史指标"],
                "href": "/target-allocation",
                "action": "打开理想仓位",
            },
            {
                "title": "组合复核",
                "steps": ["仓位框架", "仓位钻取", "候选审计", "shadow 导出"],
                "href": "/buckets/drilldown",
                "action": "打开仓位钻取",
            },
            {
                "title": "盘前策略",
                "steps": ["市场位置", "策略简报", "估值检查", "过期检查"],
                "href": "/tools?group=基金经理",
                "action": "打开基金经理工具",
            },
        ],
        "links": [
            {"label": "每日指挥台", "href": "/assistant"},
            {"label": "偏好模拟", "href": "/assistant/preferences"},
            {"label": "深度情景推演", "href": "/assistant/scenarios"},
            {"label": "市场历史", "href": "/market/history"},
            {"label": "理想仓位", "href": "/target-allocation"},
            {"label": "仓位框架", "href": "/buckets"},
            {"label": "仓位钻取", "href": "/buckets/drilldown"},
            {"label": "历史指标", "href": "/historical-metrics"},
        ],
        "tool_links": [
            {"label": "市场位置提示词", "href": "/tools?group=基金经理"},
            {"label": "目标仓位生成", "href": "/tools?group=基金经理"},
            {"label": "候选仓位审计", "href": "/tools?group=基金经理"},
        ],
    },
    "researcher": {
        "role": "researcher",
        "title": "研究员工作台",
        "subtitle": "ResearchFirst、主题、ETF 与个股研究入口。",
        "tool_group": "研究员",
        "metrics": [
            {"label": "职责", "value": "研究覆盖"},
            {"label": "门槛", "value": "ResearchFirst"},
            {"label": "模式", "value": "current-only"},
            {"label": "交易", "value": "off", "tone": "warn"},
        ],
        "workflows": [
            {
                "title": "补齐研究门槛",
                "steps": ["ResearchFirst", "标的状态", "研究缺口", "标的钻取"],
                "href": "/research-first",
                "action": "打开 ResearchFirst",
            },
            {
                "title": "主题到标的",
                "steps": ["主线研究", "龙头候选", "ETF 研究", "个股研究"],
                "href": "/themes",
                "action": "打开主线研究",
            },
            {
                "title": "缺口复盘",
                "steps": ["研究缺口", "缺口历史", "估值历史", "当前清单"],
                "href": "/history/gap-dashboard",
                "action": "打开缺口历史",
            },
        ],
        "links": [
            {"label": "每日指挥台", "href": "/assistant"},
            {"label": "研究任务闭环", "href": "/assistant/research-tasks"},
            {"label": "全局搜索", "href": "/assistant/search"},
            {"label": "ResearchFirst", "href": "/research-first"},
            {"label": "标的状态", "href": "/subjects"},
            {"label": "研究缺口", "href": "/subjects/gap"},
            {"label": "标的钻取", "href": "/subjects/drilldown"},
            {"label": "主线研究", "href": "/themes"},
            {"label": "缺口历史", "href": "/history/gap-dashboard"},
        ],
        "tool_links": [
            {"label": "主线研究提示词", "href": "/tools?group=研究员"},
            {"label": "ETF 研究提示词", "href": "/tools?group=研究员"},
            {"label": "个股研究提示词", "href": "/tools?group=研究员"},
        ],
    },
    "trader": {
        "role": "trader",
        "title": "操盘手工作台",
        "subtitle": "操作计划、盘中规则与复盘入口。",
        "tool_group": "操盘手",
        "metrics": [
            {"label": "职责", "value": "执行纪律"},
            {"label": "输出", "value": "ratio-only"},
            {"label": "模式", "value": "read-only"},
            {"label": "下单", "value": "off", "tone": "warn"},
        ],
        "workflows": [
            {
                "title": "盘前执行",
                "steps": ["只读快照", "操作计划", "盘前检查", "盘中规则"],
                "href": "/action-plan",
                "action": "打开操作计划",
            },
            {
                "title": "盘中监控",
                "steps": ["QMT 只读探测", "规则检查", "当前仓位", "决策日志"],
                "href": "/intraday-rules",
                "action": "打开盘中规则",
            },
            {
                "title": "复盘",
                "steps": ["动作历史", "仓位历史", "决策时间线", "周度复盘"],
                "href": "/decision-timeline",
                "action": "打开决策时间线",
            },
        ],
        "links": [
            {"label": "每日指挥台", "href": "/assistant"},
            {"label": "风险预警中心", "href": "/assistant/risk-center"},
            {"label": "一键盘前流程", "href": "/assistant/premarket"},
            {"label": "操作计划", "href": "/action-plan"},
            {"label": "当前仓位", "href": "/portfolio"},
            {"label": "盘中规则", "href": "/intraday-rules"},
            {"label": "仓位历史", "href": "/positions/history"},
            {"label": "动作历史", "href": "/actions/history"},
            {"label": "决策时间线", "href": "/decision-timeline"},
            {"label": "决策日志", "href": "/decision-log"},
        ],
        "tool_links": [
            {"label": "QMT 只读探测", "href": "/tools?group=操盘手"},
            {"label": "操作计划生成", "href": "/tools?group=操盘手"},
            {"label": "盘后复盘生成", "href": "/tools?group=操盘手"},
        ],
    },
    "system": {
        "role": "system",
        "title": "系统与开发工作台",
        "subtitle": "检查、导入、发布验收与只读状态入口。",
        "tool_group": "系统与开发",
        "metrics": [
            {"label": "职责", "value": "系统维护"},
            {"label": "数据库", "value": "temp-only"},
            {"label": "模式", "value": "current-only"},
            {"label": "交易", "value": "off", "tone": "warn"},
        ],
        "workflows": [
            {
                "title": "日常刷新",
                "steps": ["重建索引", "刷新 Web DB", "系统检查", "Web 冒烟"],
                "href": "/tools?group=系统与开发",
                "action": "打开系统工具",
            },
            {
                "title": "发布验收",
                "steps": ["项目检查", "ratio-only", "ResearchFirst", "Web 发布验收"],
                "href": "/system-checks",
                "action": "打开系统检查",
            },
            {
                "title": "状态审计",
                "steps": ["Readiness", "环境状态", "偏好设置", "审计导出"],
                "href": "/readiness",
                "action": "打开 Readiness",
            },
        ],
        "links": [
            {"label": "每日指挥台", "href": "/assistant"},
            {"label": "复盘评分", "href": "/assistant/review-score"},
            {"label": "安全周报", "href": "/assistant/weekly-safety"},
            {"label": "系统检查", "href": "/system-checks"},
            {"label": "工具注册表", "href": "/tools"},
            {"label": "Readiness", "href": "/readiness"},
            {"label": "环境状态", "href": "/environment"},
            {"label": "偏好设置", "href": "/preferences"},
            {"label": "审计导出", "href": "/audit"},
        ],
        "tool_links": [
            {"label": "刷新 Web 数据库", "href": "/tools?group=系统与开发"},
            {"label": "项目当前态检查", "href": "/tools?group=系统与开发"},
            {"label": "Web 发布验收", "href": "/tools?group=系统与开发"},
        ],
    },
}


class RoleWorkbenchService:
    def get(self, role: str) -> dict[str, object]:
        if role not in ROLE_WORKBENCHES:
            raise KeyError(f"Unknown role workbench: {role}")
        return deepcopy(ROLE_WORKBENCHES[role])
