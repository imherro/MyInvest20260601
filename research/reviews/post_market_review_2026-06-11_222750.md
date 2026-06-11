# 盘后复盘

日期：2026-06-11
生成时间：2026-06-11_222750
类型：daily_brief

## 1. 结论

已自动生成盘后复盘底稿；缺少实际执行记录时只做计划/规则/风险复盘，不假设已执行。

| 项目 | 状态 |
| --- | --- |
| 复盘结论 | insufficient_information |
| 是否需要研究更新 | True |
| 是否需要规则修正 | False |

## 2. 市场判断复盘

- 盘前判断：极弱/风险收缩; 权益目标 30%-40%; Target equity is 30%-40%; actual equity is about 43.02%. Allowed actions are ratio-only risk reduction and cash/short-duration restoration; no direct single-name add is allowed without fresh dossiers.
- 收盘表现：未接入收盘行情自动拉取；本脚本只引用已落盘市场报告和盘中提醒。
- 偏差评估：cannot_judge_close_bias_without_close_data
- 原因：需要盘后市场数据或用户确认后再判断市场预判偏差。

## 3. 操作计划复盘

| 对象 | 事前建议 | 条件触发 | 是否执行 | 结果 |
| --- | --- | --- | --- | --- |
| overall equity exposure | Reduce reduce 3.0pp to 8.0pp | manual confirmation and no newer upstream file | None | 等待用户提供实际执行信息；未提供前不能假设已执行。 |
| cash/short-duration bucket | Add increase 3.0pp to 8.0pp | paired with equity-risk reduction | None | 等待用户提供实际执行信息；未提供前不能假设已执行。 |
| 其他/待清理 | Reduce reduce in stages before considering core adds | profile/liquidity/manual review before single-name action | None | 等待用户提供实际执行信息；未提供前不能假设已执行。 |

## 4. 组合风险变化

- 权益仓变化：最新快照权益约 43.0201%，目标由 action_plan/target_allocation 约束。
- 主题/行业集中：未生成盘后新持仓快照前，只能沿用最新快照。
- 单标的风险：未发现自动化脚本可确认的新增单标的超限。

## 5. 估值更新检查

检查命令：`python scripts/check_valuation_updates.py --intraday-report temp/runtime/alerts/intraday_once.json`

| 代码 | 名称 | 状态 | 原因 |
| --- | --- | --- | --- |
| 513180.SH | 恒生科技ETF华夏 | update | 实时价格已跨估值区：报告=价格合理区，实时=价格偏贵区 |

## 6. 需要更新的研究

| 模块/文件 | 是否需要 | 优先级 | 原因 |
| --- | --- | --- | --- |
| valuation_report | True | high | 发现 1 个估值报告缺失、过期或盘中跨区项；新增单标的动作前应先确认是否刷新估值报告。 |
| portfolio_snapshot | False | medium | 若今日有实际执行，应刷新QMT只读持仓快照。 |

## 7. 明日观察

- 权益仓是否仍高于45%。
- 现金/短融是否回到55%-60%。
- legacy_watch 是否按操作建议进入第一阶段清理。
- 市场门禁是否从 verify_only/risk_reduce_only 改善到允许新增风险。

## 8. 决策日志条目

```text
2026-06-11 盘后复盘自动底稿：生成 post_market_review_2026-06-11_222750.md/json；读取最新 market/theme/action/portfolio/alerts，并运行估值更新检查；缺少执行记录时不判断已执行。
```
