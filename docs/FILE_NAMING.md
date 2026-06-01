# 文件命名与版本规则

本文定义研究产物的文件命名规则。目标是保留每次研究版本，同时让后续研究默认读取最新版本。

## 1. 核心规则

所有研究报告类文件名必须包含日期和时间戳：

```text
YYYY-MM-DD_HHMMSS
```

示例：

```text
market_score_2026-06-01_093000.md
market_score_2026-06-01_093000.json
theme_review_2026-06-01_210500.md
theme_review_2026-06-01_210500.json
action_plan_2026-06-01_091500_premarket.md
```

时间戳使用本地工作时区。当前项目环境通常为 `Asia/Shanghai`。

## 2. 为什么必须加时间戳

- 同一天可能多次更新市场仓位、主线、组合或操作建议。
- 只用日期会覆盖旧版本，无法回看当时判断。
- 带时间戳后，可以比较早盘、盘中、盘后和临时事件更新的差异。

## 3. 默认读取最新版本

基于前期研究做新研究时，默认读取同类文件中时间戳最新的版本。

例如：

```text
research/market/market_score_2026-06-01_093000.md
research/market/market_score_2026-06-01_133000.md
```

后续操作建议默认读取：

```text
market_score_2026-06-01_133000.md
```

除非用户明确要求读取某个历史版本。

## 4. 固定状态文件例外

以下文件可以使用固定文件名，因为它们代表“当前状态”：

```text
research/themes/theme_registry.json
research/etfs/etf_registry.json
research/stocks/stock_registry.json
research/logs/decision_log.md
research/portfolio/current_holdings_template.md
```

固定状态文件更新时，仍然必须在对应研究报告或决策日志中保留变化记录。

## 5. 推荐命名

### 市场仓位

```text
research/market/market_score_YYYY-MM-DD_HHMMSS.md
research/market/market_score_YYYY-MM-DD_HHMMSS.json
```

### 主线研究

```text
research/themes/theme_review_YYYY-MM-DD_HHMMSS.md
research/themes/theme_review_YYYY-MM-DD_HHMMSS.json
```

### ETF 档案

```text
research/etfs/ETF代码_名称_YYYY-MM-DD_HHMMSS.md
research/etfs/ETF代码_名称_YYYY-MM-DD_HHMMSS.json
```

### 个股档案

```text
research/stocks/股票代码_名称_YYYY-MM-DD_HHMMSS.md
research/stocks/股票代码_名称_YYYY-MM-DD_HHMMSS.json
```

### 组合分析

```text
research/portfolio/portfolio_snapshot_YYYY-MM-DD_HHMMSS.md
research/portfolio/portfolio_snapshot_YYYY-MM-DD_HHMMSS.json
```

### 操作建议

```text
research/actions/action_plan_YYYY-MM-DD_HHMMSS_premarket.md
research/actions/action_plan_YYYY-MM-DD_HHMMSS_premarket.json
research/actions/action_plan_YYYY-MM-DD_HHMMSS_close.md
research/actions/action_plan_YYYY-MM-DD_HHMMSS_close.json
```

### 盘中提醒

```text
research/alerts/intraday_alert_YYYY-MM-DD_HHMMSS.md
research/alerts/intraday_alert_YYYY-MM-DD_HHMMSS.json
```

### 盘后复盘

```text
research/reviews/post_market_review_YYYY-MM-DD_HHMMSS.md
research/reviews/post_market_review_YYYY-MM-DD_HHMMSS.json
research/reviews/post_market_review_YYYY-MM-DD_HHMMSS_weekly.md
```

## 6. 新研究开始前必须做

1. 找到本模块最新版本文件。
2. 明确写出读取了哪个版本。
3. 如果不用最新版本，必须说明原因。
4. 新产物使用新的时间戳，不覆盖旧文件。

## 7. 决策日志要求

重要研究更新必须写入 `research/logs/decision_log.md`，并注明：

- 本次生成文件名。
- 读取的前置研究文件名。
- 是否为同类最新版本。
- 如果不是最新版本，原因是什么。
