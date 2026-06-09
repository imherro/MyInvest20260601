# 估值研究模块

版本：v1.0

本模块用于单独生成 ETF 和个股的估值区间报告，并把关键分段写入盘中监测规则。它不替代 ETF 档案、个股档案、市场仓位报告或 ACTION_PLAN。

## 1. 模块边界

- ETF/个股档案：解释资产属性、估值方法、估值锚、风险和条件化策略。
- 估值报告：给出当前价格/净值位置、低估观察区、合理配置区、偏贵区、拥挤/风险区。
- 标的级估值状态：给出 `低估`、`合理`、`偏贵`、`泡沫` 四类提示，但只代表标的自身估值/赔率位置。
- ACTION_PLAN：结合市场仓位、组合暴露和触发条件，生成最终买入、加仓、减仓或卖出动作。
- 盘中作战地图：只展示估值分段和触发状态，不临时生成新策略，不自动下单。

标的级估值状态不得读取或依赖用户真实持仓，也不得依赖总体仓位位置。它只基于该 ETF/个股自身的估值、趋势、基本面、拥挤度和风险条件。组合级最终动作仍由 ACTION_PLAN 决定。

## 2. 分段定义

每个标的必须输出四段：

| 分段 | 含义 | 默认动作边界 |
| --- | --- | --- |
| 低估观察区 | 价格/估值已进入赔率较好区域，但仍需趋势、资金和基本面确认 | 低估 |
| 合理配置区 | 估值与风险收益较均衡，是否配置取决于市场仓位和组合暴露 | 合理 |
| 偏贵区 | 赔率下降，不宜因为趋势强就盲目新增 | 偏贵 |
| 拥挤/风险区 | 估值或价格位置过高，容易出现回撤或拥挤踩踏 | 泡沫 |

## 3. 数据口径

宽基 ETF 优先使用：

- 跟踪指数 PE/PB 分位。
- ETF 历史价格/净值位置。
- ETF 折溢价。
- ETF 历史趋势、前高回撤和前低反弹必须优先使用 Tushare `fund_nav.adj_nav` 复权净值序列；缺失时依次回退 `accum_nav`、`unit_nav`，最后才允许使用交易价格代理，并必须标记低可信度。

主题 ETF 优先使用：

- 跟踪指数估值分位，如可取得。
- ETF 历史价格/净值位置。
- ETF 净值位置。
- 数据不足时必须标记为“价格/净值位置代理”，不能写成已确认长期估值。
- 发生分红、拆分或除权的 ETF，不得用未复权交易收盘价直接计算历史回撤/反弹，否则会把除权缺口误判成真实下跌。

个股优先使用：

- PE_TTM、PB、PS_TTM 历史分位。
- 资产类型适配后的估值锚。
- 同业比较或资产属性比较。
- 上市不足 3 年时，历史分位只能作为弱参考。

## 4. 输出路径

标准输出：

```text
research/valuations/valuation_{代码}_{名称}_YYYY-MM-DD_HHMMSS.md
research/valuations/valuation_{代码}_{名称}_YYYY-MM-DD_HHMMSS.json
```

盘中监测同步：

```text
research/alerts/intraday_rules.json
```

写入字段：

```json
{
  "valuation_visual": {
    "metric": "price",
    "current_value": 0,
    "current_zone": "reasonable_allocation",
    "zones": [
      {"key": "undervalued_observe", "label": "低估观察区", "min": 0, "max": 0, "color": "#2f9e44"},
      {"key": "reasonable_allocation", "label": "合理配置区", "min": 0, "max": 0, "color": "#74b816"},
      {"key": "expensive", "label": "偏贵区", "min": 0, "max": 0, "color": "#f59f00"},
      {"key": "crowded_risk", "label": "拥挤/风险区", "min": 0, "max": 0, "color": "#e03131"}
    ]
  }
}
```

ETF 使用复权净值或其他可比序列时，必须同步写入序列口径，供盘中作战地图解释图示：

```json
{
  "price_series": {
    "basis": "adj_nav",
    "basis_label": "复权净值",
    "comparable": true,
    "display_price_basis": "qmt_realtime_price",
    "realtime_price_multiplier": 1.0,
    "factor_date": "YYYYMMDD",
    "note": "历史趋势和回撤用复权净值；盘中实时价按最近净值/单位净值比例换算成可比口径。"
  }
}
```

`valuation_visual.zones`、风控位、右侧确认位和风险区起点应落在盘中实时交易价格可直接比较的价格刻度上；`trend_visual` 的历史回撤/反弹可以保留在复权净值可比刻度上，但必须提供 `price_series` 说明。

标的级估值状态字段：

```json
{
  "security_stance": {
    "label": "低估|合理|偏贵|泡沫",
    "basis": "估值、趋势、基本面或拥挤度依据",
    "confidence": "高|中|低|中高|中低",
    "scope": "security_level_only",
    "not_portfolio_action": true
  }
}
```

趋势和回撤/反弹字段必须由本模块或趋势研究上游提前生成，供盘中作战地图直接绘图：

```json
{
  "trend_visual": {
    "trends": [
      {"key": "long", "label": "长期", "state": "上行|震荡|下行|样本不足", "change_pct": 0},
      {"key": "mid", "label": "中期", "state": "上行|震荡|下行|样本不足", "change_pct": 0},
      {"key": "short", "label": "短期", "state": "上行|震荡|下行|样本不足", "change_pct": 0}
    ],
    "drawdown": {
      "from_sample_high_pct": 0,
      "common_120d_drawdown_pct": 0,
      "deep_120d_drawdown_pct": 0,
      "max_120d_drawdown_pct": 0
    },
    "rebound": {
      "from_sample_low_pct": 0,
      "common_120d_rebound_pct": 0,
      "strong_120d_rebound_pct": 0,
      "max_120d_rebound_pct": 0
    }
  }
}
```

若上述字段缺失，盘中作战地图只能显示缺失提示，不得在盘中临时补算研究结论。

## 5. 更新频率

估值报告分为两类更新：

1. 轻量检查：盘前、盘中、盘后都应运行或引用 `scripts/check_valuation_updates.py`，覆盖最新持仓和作战地图监控标的。若报告缺失、基准日过旧，或盘中实时价格已跨出报告基准区间，必须提示用户是否更新估值报告。
2. 完整重算：不要求每天全量重做所有 ETF/个股估值。完整重算由跨区、显著异动、财报/公告、指数估值口径更新、或周期性复核触发。

盘中窗口只显示“实时区间”和“报告基准区间”的差异，不在盘中重算完整估值报告。

## 6. 使用提示词

```text
请按 docs/modules/VALUATION_RESEARCH.md 生成这些标的的估值报告。
必须使用 Tushare 优先，输出 timestamped Markdown + JSON。
ETF 必须区分真实指数估值和价格/净值位置代理。
个股必须给出估值区间或估值锚，但不生成组合级买卖动作。
生成后同步更新 research/alerts/intraday_rules.json，使盘中作战地图能显示估值分段图示。
```
