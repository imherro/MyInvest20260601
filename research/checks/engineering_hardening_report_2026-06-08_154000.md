# 工程硬化报告

生成时间：2026-06-08_154000

## 1. 本轮修复边界

本轮只修工程约束，不重算投资结论，不生成新的买卖建议。

目标是让系统先具备三类门禁：

- 知道每个当前文件是否引用了旧上游。
- 知道仓位数学和持仓数据质量是否可用。
- 在过期或数据异常时，盘中监控只能观察和风险复核，不能输出买入/加仓类动作。

## 2. 已修复内容

| 模块 | 修复 |
| --- | --- |
| 最新文件索引 | 新增 `scripts/build_latest_index.py`，生成 `research/latest_index.json`，以 `generated_at / basis_trade_date / sha256` 判断最新，不再依赖文件修改时间。 |
| stale 检查 | 新增 `scripts/check_staleness.py`，检查当前最新链条和活跃盘中规则是否引用旧上游。 |
| 项目门禁 | 增强 `scripts/project_check.py`，检查关键脚本、盘中规则引用、仓位数学、QMT 价格异常和 stale 状态。 |
| review package | 新增 `scripts/build_review_package.py`，打包后回读 zip，校验 FILE_LIST、manifest、实际 zip 内容一致。 |
| 桶配置 | 新增 `research/config/bucket_registry.json`，集中维护仓位桶、颜色、代码归属和分类归属。 |
| QMT 持仓快照 | `scripts/qmt_portfolio_snapshot.py` 新增 `quality` 字段；`cost_price/current_price <= 0` 会置空并进入质量错误；同步盘中规则时检查目标配置是否 stale。 |
| 盘中提醒 | `scripts/intraday_monitor.py` 新增 `priority_score`，并在规则 stale/degraded/blocked 时阻断买入/加仓类提醒。 |
| 作战地图 | `scripts/intraday_dashboard.py` 顶部新增规则新鲜度状态；stale/degraded 时明确提示只能观察和风险复核。 |
| 估值脚本 | `scripts/generate_valuation_reports.py` 删除旧 market_score/target_allocation 硬编码路径，改为读取 latest_index；主题 ETF 只有价格代理时输出价格位置语义。 |
| 数据质量 | 已将 2026-06-08 QMT 快照中 159301 的负成本价置空，并记录质量错误。 |

## 3. 当前最新上游

| 模块 | 最新文件 |
| --- | --- |
| market_score | `research/market/market_score_2026-06-08_100643.json` |
| theme_review | `research/themes/theme_review_2026-06-08_102237.json` |
| portfolio_snapshot | `research/portfolio/portfolio_snapshot_2026-06-08_135053.json` |
| target_allocation | `research/allocation/target_allocation_2026-06-03_211833.json` |
| intraday_rules | `research/alerts/intraday_rules.json` |
| staleness_check | `research/checks/staleness_check_2026-06-08_153845.json` |

## 4. 当前仍 stale 的关键问题

| 文件 | 问题 | 影响 |
| --- | --- | --- |
| `research/allocation/target_allocation_2026-06-03_211833.json` | 仍引用 6 月 3 日市场仓位、旧持仓和旧主线；权益中心 47.5% 不在最新市场仓位 40%-45% 区间内。 | 目标配置不可作为当前加仓依据。 |
| `research/alerts/intraday_rules.json` | 仍引用 6 月 3 日目标配置和 6 月 3 日市场仓位。 | 作战地图已标记 stale，只能观察和风险复核。 |
| `research/actions/action_plan_2026-06-03_201848_rare_metals_group.json` | 操作建议引用旧市场、旧持仓、旧主线。 | 当前不应直接使用该 action_plan。 |

## 5. 自检结果

| 检查 | 结果 |
| --- | --- |
| `python -m py_compile scripts/*.py` | 通过 |
| `python scripts/build_latest_index.py` | 通过，已生成 `research/latest_index.json` |
| `python scripts/check_staleness.py --rebuild-index --write-report --update-intraday-rules` | 通过，当前状态 `stale`，0 error，12 stale |
| `python scripts/project_check.py` | 0 FAIL，2 WARN |
| `python scripts/build_review_package.py` | 通过，zip 内容与清单一致 |

## 6. 下一阶段

下一阶段才进入重建投资链条：

1. 用最新 market_score 和 theme_review 重建 target_allocation。
2. 用最新 QMT portfolio_snapshot 同步新的 intraday_rules。
3. 将旧 action_plan / premarket_check 标记为 stale，不再作为操作依据。
4. 如果需要新的买卖建议，再基于新 target_allocation 生成新的 action_plan。

