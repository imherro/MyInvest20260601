# 主线龙头候选池模块

职责：在主线研究确认后，把相关 ETF 和代表个股自动分流为候选池、ResearchFirst 清单和可复核清单。

本模块不判断主线本身是否正确，不临时改写主线评级，也不直接生成买入、加仓、减仓或卖出建议。

## 触发条件

- 主线研究更新后。
- 用户确认某条主线进入 A / A- / B+ 交易评级后。
- 盘前或操作建议模块发现某条主线缺少对应 ETF / 个股档案时。

## 输入

- `research/themes/theme_registry.json`
- `research/etfs/etf_registry.json`
- `research/stocks/stock_registry.json`
- `research/valuations/` 下的最新估值报告
- 可选：Tushare `stock_basic`，用于把代表股票名称解析为 A 股代码。

## 默认确认门槛

默认只有满足以下条件的主线，才进入“确认主线候选池”：

- `status = active`
- 当前 A 股交易评级为 `A`、`A-` 或 `B+`
- 阶段不是 `decline`

普通 `B` 代表仍有交易价值或观察价值，但默认不自动进入进攻复核。需要放宽时，运行脚本时显式使用 `--include-b`。

## 分流规则

每个候选 ETF / 个股只进入以下一种状态：

| 状态 | 含义 | 后续动作 |
| --- | --- | --- |
| `ready_for_review` | 主线已确认，已有档案，已有估值报告 | 可进入盘前、盘中和操作建议模块复核 |
| `ResearchFirst.valuation_missing` | 主线已确认，已有档案，但缺少估值报告 | 先补估值，再进入操作复核 |
| `ResearchFirst.profile_missing` | 主线已确认，但缺少 ETF / 个股档案 | 先建档，不给操作建议 |
| `ResearchFirst.code_unresolved` | 代表股票只有名称，未能解析代码 | 先确认代码，再建档 |
| `watch_only.theme_not_confirmed` | 所属主线未达 A / A- / B+ 交易确认 | 仅观察，不进入操作复核 |

## 输出

- `research/theme_leaders/theme_leaders_YYYY-MM-DD_HHMMSS.md`
- `research/theme_leaders/theme_leaders_YYYY-MM-DD_HHMMSS.json`

输出必须包含：

- 使用的主线确认门槛。
- 每条主线的战略评级、交易评级和阶段。
- ETF 候选和个股候选的分流状态。
- 缺失档案、缺失估值、代码未解析的 ResearchFirst 清单。
- 明确声明：候选池不是可买清单。

## 禁止事项

- 不因为主线强就自动把所有相关龙头标为买入。
- 不绕过个股档案、ETF 档案和估值报告。
- 不把战略主线评级当成当前交易评级。
- 不从新闻热度临时扩展大量未经验证的“龙头名单”。
