# 模块架构

本文定义本项目的模块边界。原则是：每个模块只解决一个层级的问题，研究结论先保存，后续建议必须引用已有结论。

## 总流程

```text
读取项目记忆和已有研究
→ 更新市场仓位
→ 更新主线研究
→ 更新 ETF/个股档案
→ 分析当前组合
→ 生成操作建议
→ 记录决策日志
→ 盘后复盘
```

操作建议模块不能绕过前置研究直接给出买卖结论。

## 01 市场仓位模块

职责：决定当前总权益仓位区间。

核心问题：

- 当前适合多少股票/ETF 权益仓位？
- 债券、短融、现金类仓位应该保留多少？
- 当前市场是进攻、防守还是观望？

输入：

- 指数趋势
- 市场广度
- 成交量与流动性
- 资金流与风险偏好
- 主线强度
- 估值赔率
- 宏观政策环境
- 拥挤惩罚

输出：

- 市场机会分数
- 拥挤惩罚
- 市场仓位分数
- 建议权益仓位区间
- 债券/现金仓位区间
- 主要风险
- 对进攻仓的限制

更新频率：

- 盘前每日简版
- 周末完整版
- 重大政策、暴跌、暴涨时临时更新

禁止事项：

- 不推荐具体股票。
- 不临时改写主线评级。
- 不因为单日大涨大跌直接推翻仓位框架。

## 02 主线研究模块

职责：判断 A 股当前主线、主线等级和变化原因。

核心问题：

- 当前 A/B/C/D 档主线分别是什么？
- 哪些主线上调、下调、维持、移出或新增？
- 哪些方向可以进入进攻仓？

输入：

- 行业和主题表现
- ETF 趋势和成交
- 龙头股强度
- 产业逻辑
- 政策催化
- 资金参与程度
- 板块内部扩散情况

输出：

- 主线评级
- 主线评分
- 变化类型
- 变化原因
- 对仓位的影响
- 对应 ETF 和龙头观察池

更新频率：

- 每周完整版
- 盘前只做重大变化检查
- 重大事件时临时更新

禁止事项：

- 不在操作建议中临时重写主线。
- 不把短期主题暴涨直接升级为 A 档。
- 不只根据新闻热度给主线评级。

## 03 ETF 研究模块

职责：单独分析每只 ETF 的角色、估值、趋势、风险和操作条件。

核心问题：

- 这只 ETF 属于核心仓、进攻仓、防御仓还是主题仓？
- 当前适合买、持有、加仓、减仓还是观察？
- 它对应的主线或指数是否仍然有效？

输入：

- 跟踪指数
- 成分结构
- 估值分位
- 趋势状态
- 成交和资金流
- 对应主线评级
- 与组合中其他资产的重叠度

输出：

- ETF 角色
- 当前评级
- 目标仓位区间
- 买入条件
- 加仓条件
- 减仓条件
- 失效条件

更新频率：

- 每周或触发条件更新
- 主线评级变化时更新
- 估值或趋势明显变化时更新

禁止事项：

- 不把 ETF 当成单一个股分析。
- 不忽略成分股重叠导致的集中风险。
- 不用短期涨跌替代指数估值和结构判断。

## 04 个股研究模块

职责：单独分析每只股票的商业逻辑、估值、业绩、风险和操作条件。

核心问题：

- 这家公司是否值得持有？
- 当前价格是否有赔率？
- 买入逻辑是否仍然成立？
- 触发减仓或卖出的条件是什么？

输入：

- 公司业务
- 行业景气
- 财务和业绩预期
- 估值区间
- 竞争格局
- 风险事件
- 技术状态
- 所属主线评级

输出：

- 投资逻辑
- 估值判断
- 当前评级
- 目标仓位区间
- 买入条件
- 加仓条件
- 减仓条件
- 卖出/失效条件
- 核心风险

更新频率：

- 财报后更新
- 重大公告后更新
- 价格或估值明显偏离时更新
- 主线降级时检查

禁止事项：

- 不只因为所属主线强就忽视个股估值和风险。
- 不把短线交易理由包装成长线逻辑。
- 不给没有失效条件的买入建议。

## 05 组合分析模块

职责：判断当前持仓是否匹配市场仓位、主线评级和风险约束。

核心问题：

- 当前权益仓位是否过高或过低？
- 核心仓、进攻仓、防御仓、主题仓比例是否合理？
- 行业和单一主线是否过度集中？
- 持仓是否与已固化研究结论一致？

输入：

- 当前持仓
- 现金/债券仓位
- 市场仓位分数
- 主线评级
- ETF 档案
- 个股档案
- 硬约束

输出：

- 当前组合偏离
- 需要调整的仓位
- 风险暴露
- 优先处理项
- 不建议操作项

更新频率：

- 每次操作前
- 每周完整版
- 组合发生明显变化后

禁止事项：

- 不绕过市场仓位和主线结论直接推荐买卖。
- 不只看单个标的，忽略组合整体风险。

## 06 操作建议模块

职责：基于前置研究成果，给出具体买、卖、加、减、持有、观察建议。

核心问题：

- 今天是否需要操作？
- 如果操作，操作哪个标的、多少仓位、为什么？
- 如果不操作，是因为没有机会、等待确认，还是风险过高？

输入：

- 市场仓位结论
- 主线研究结论
- ETF/个股档案
- 组合分析
- 盘中触发条件

输出：

- 操作类型
- 标的
- 建议仓位变化
- 依据
- 失效条件
- 风险提示
- 复盘点

更新频率：

- 盘前
- 盘中触发条件出现时
- 盘后复盘前

禁止事项：

- 不凭空给建议。
- 不重写市场仓位或主线评级。
- 不给没有依据、没有条件、没有复盘点的操作。

## 07 盘中提醒模块

职责：监控已定义触发条件，并提醒是否需要执行原计划。

核心问题：

- 是否触发买入、加仓、减仓、止损、止盈或观察条件？
- 触发后是执行、等待确认，还是取消？

输入：

- 盘前操作计划
- 持仓标的触发条件
- 观察池触发条件
- 市场仓位限制
- 主线状态

输出：

- 触发提醒
- 对应原计划
- 建议动作
- 是否需要人工确认

更新频率：

- 盘中按触发条件

禁止事项：

- 不在盘中临时发明新策略。
- 不因为价格波动频繁改变原计划。

## 08 盘后复盘模块

职责：记录当天市场表现、操作执行、判断偏差和后续修正。

核心问题：

- 盘前判断是否正确？
- 操作是否执行？
- 执行是否符合计划？
- 哪些判断需要修正？

输入：

- 盘前分析
- 盘中提醒
- 实际操作
- 收盘市场表现
- 持仓表现

输出：

- 当日复盘
- 判断偏差
- 执行偏差
- 需要更新的研究文件
- 第二天观察重点

更新频率：

- 每日简版
- 周末完整版

禁止事项：

- 不只记录涨跌结果。
- 不把单日结果简单归因为策略正确或错误。

## 09 决策日志模块

职责：保存关键结论变化和操作理由，形成长期可追溯记录。

核心问题：

- 什么时候做了什么判断？
- 判断为什么变化？
- 当时依据是什么？
- 后来结果如何？

输入：

- 市场仓位变化
- 主线评级变化
- ETF/个股评级变化
- 操作建议
- 实际操作
- 复盘结论

输出：

- 日期
- 决策类型
- 原结论
- 新结论
- 变化原因
- 对仓位或操作的影响
- 后续复盘入口

更新频率：

- 每次重要结论变化后
- 每次实际操作后
- 每次规则修订后

禁止事项：

- 不覆盖旧记录。
- 不只记录结论，不记录原因。

## 文件产物建议

```text
research/
  market/
    market_score_YYYY-MM-DD.md
    market_score_YYYY-MM-DD.json
  themes/
    theme_review_YYYY-MM-DD.md
    theme_review_YYYY-MM-DD.json
    theme_registry.json
  etfs/
    ETF代码_名称.md
    ETF代码_名称.json
  stocks/
    股票代码_名称.md
    股票代码_名称.json
  portfolio/
    portfolio_snapshot_YYYY-MM-DD.md
    portfolio_snapshot_YYYY-MM-DD.json
  actions/
    action_plan_YYYY-MM-DD_premarket.md
    action_plan_YYYY-MM-DD_premarket.json
    action_plan_YYYY-MM-DD_close.md
    action_plan_YYYY-MM-DD_close.json
  logs/
    decision_log.md
```

## 当前优先级

第一阶段先完成：

1. 市场仓位模块模板（已建立：`docs/modules/MARKET_POSITION.md`、`templates/market_score_template.md`、`templates/market_score_template.json`）
2. 主线研究模块模板（已建立：`docs/modules/THEME_RESEARCH.md`、`templates/theme_review_template.md`、`templates/theme_review_template.json`、`research/themes/theme_registry.json`）
3. ETF 档案模板（已建立：`docs/modules/ETF_RESEARCH.md`、`templates/etf_profile_template.md`、`templates/etf_profile_template.json`、`research/etfs/etf_registry.json`）
4. 个股档案模板（已建立：`docs/modules/STOCK_RESEARCH.md`、`templates/stock_profile_template.md`、`templates/stock_profile_template.json`、`research/stocks/stock_registry.json`）
5. 决策日志模板（已建立：`docs/modules/DECISION_LOG.md`、`templates/decision_log_entry_template.md`、`templates/decision_log_entry_template.json`、`research/logs/decision_log.md`）
6. 组合分析模块模板（已建立：`docs/modules/PORTFOLIO_ANALYSIS.md`、`templates/portfolio_snapshot_template.md`、`templates/portfolio_snapshot_template.json`、`research/portfolio/current_holdings_template.md`）
7. 操作建议模块模板（已建立：`docs/modules/ACTION_PLAN.md`、`templates/action_plan_template.md`、`templates/action_plan_template.json`）

暂时不做：

- 自动化行情接入
- SQLite 数据库
- 复杂回测
- 盘中自动交易
