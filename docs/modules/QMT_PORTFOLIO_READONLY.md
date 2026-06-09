# QMT只读持仓模块

## 目标

从本机 QMT / XtQuant 交易接口读取真实持仓，并生成系统可用的 `portfolio_snapshot_YYYY-MM-DD_HHMMSS.md/json`。

## 安全边界

本模块只调用只读接口：

- `query_account_infos`
- `query_account_status`
- `query_stock_asset`
- `query_stock_positions`

禁止调用下单、撤单、改单等交易接口。

## 隐私口径

允许保存：

- 证券代码、名称、类型
- 仓位比例
- 当日涨跌幅
- 参考盈亏比例
- 成本价
- 原始负成本价，仅用于审计本金已收回状态
- 成本状态
- 现价
- 分类和仓位桶

禁止保存：

- 市值
- 现金金额
- 成本金额
- 盈亏金额
- 持仓数量
- 可用数量
- 冻结数量
- 账号全号

账号只允许保存脱敏形式，例如 `****1234`。

## 成本字段处理

QMT 可能在本金已经收回的持仓上返回负成本价。此时不应把它当作数据错误，也不应直接用负成本计算盈亏比例。

处理规则：

- 若 `cost_price < 0` 且 `current_price > 0`，标记为 `cost_basis_status = principal_recovered`。
- 该标的 `cost_price` 写为 `0.0`，Markdown 显示为“本金已收回”。
- `raw_cost_price` 保留 QMT 返回的原始负值，仅用于审计。
- `reference_pnl_pct` 置空，不计算百分比。
- 该情况不进入 `quality.warnings`，不导致盘中规则降级。

边界：本金已收回只说明成本口径特殊，不代表该持仓没有市值风险；仓位比例、现价和盘中估值区间仍正常参与组合分析。

## 使用方式

前提：

- QMT 已打开并登录。
- 启动 QMT 时勾选“独立交易”。
- 本机可用 Python 3.11 和 QMT 自带 `xtquant`。

命令：

```powershell
py -3.11 scripts\qmt_portfolio_snapshot.py
```

或双击：

```text
refresh_qmt_portfolio_snapshot.bat
```

仅测试连接、不写文件：

```powershell
py -3.11 scripts\qmt_portfolio_snapshot.py --probe
```

如果自动发现账号失败，可在本地 `.env` 中配置：

```text
QMT_ACCOUNT_ID=你的资金账号
QMT_SITE_PACKAGES=D:\...\python\Lib\site-packages
QMT_USERDATA_DIR=D:\...\userdata_mini
```

`.env` 不提交到 GitHub。

## 与其他模块同步

生成快照后，默认同步：

- `research/alerts/intraday_rules.json` 的实际仓位覆盖层
- 每个盘中监控标的的 `current_position_pct`

因此作战地图会使用最新 QMT 真实持仓比例。

如只想生成快照、不更新作战地图规则：

```powershell
py -3.11 scripts\qmt_portfolio_snapshot.py --no-sync-rules
```
