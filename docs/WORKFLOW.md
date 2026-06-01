# 协作规则

本文说明多台电脑协同使用本项目时的规则。目标是避免不同电脑上的 Codex 不知道项目进展，也避免重要策略决议散落在聊天记录里。

## 1. 每次开始工作前

1. 拉取最新项目。
2. 阅读 `README.md`。
3. 阅读 `docs/PROJECT_MEMORY.md`。
4. 阅读 `docs/RUNBOOK.md`。
5. 阅读 `docs/DATA_SOURCES.md`，确认数据源权限。
6. 查看最近提交记录，确认上次工作到哪里。
7. 如果本次任务会改变策略、流程或研究结论，先确认应更新哪个文件。

建议对 Codex 的开场指令：

```text
请先阅读 README.md、docs/PROJECT_MEMORY.md、docs/MODULES.md、docs/RUNBOOK.md、docs/DATA_SOURCES.md 和 research/logs/decision_log.md，了解本项目已经确定的投资策略、模块边界、运行流程、数据源权限和协作规则。之后再继续当前任务。
```

## 2. 文件职责

- `README.md`：项目入口，说明新电脑如何开始。
- `docs/PROJECT_MEMORY.md`：长期记忆，记录策略框架、重要决议、错误教训。
- `docs/RUNBOOK.md`：日常运行手册，说明盘前、盘中、盘后、周末如何运行项目。
- `docs/DATA_SOURCES.md`：数据源与权限，记录 Tushare 等数据源的使用规则和本地配置方式。
- `docs/WORKFLOW.md`：协作规则，记录如何使用 Codex、如何更新文件、如何提交。
- `research/`：后续保存具体研究成果。

## 3. Codex 工作规则

Codex 不应直接从零开始给出最终买卖建议。标准顺序是：

```text
读取已有研究成果
→ 更新对应模块
→ 标记结论变化
→ 说明变化原因
→ 给出对仓位或操作的影响
→ 写入研究文件或项目记忆
→ 提交 Git commit
```

操作建议必须引用已有研究结论，例如市场仓位分数、主线评级、ETF 档案、个股档案、当前持仓结构。

## 4. 新决议如何记录

当形成新的策略决议时，更新 `docs/PROJECT_MEMORY.md` 的对应章节，并在“决议记录”中增加日期和要点。

示例：

```text
### 2026-06-05

- 将主题仓上限从 10% 调整为 8%。
- 原因：复盘发现主题仓波动对组合影响过大，且持续性不足。
- 影响：后续机器人、商业航天、无人驾驶等只允许低仓试错。
```

## 5. 研究结论如何记录

后续研究文件应同时保留：

- 当前结论
- 上一次结论
- 变化类型：维持、上调、下调、移出、新增
- 变化原因
- 对仓位或操作的影响
- 下次需要观察的触发条件

不要只覆盖旧结论。

## 6. Git 使用规则

每次完成一个清晰阶段后提交一次 commit。

推荐提交类型：

```text
docs: update project memory
strategy: revise market position rules
research: update theme review
portfolio: update position analysis
workflow: refine collaboration rules
```

提交前检查：

1. 没有提交 `.env` 或本地密钥。
2. 重要决议已经写入 `docs/PROJECT_MEMORY.md`。
3. 研究结论没有只覆盖旧记录，而是保留变化原因。
4. commit message 能看出本次变更目的。

## 7. 多电脑协同建议

- 开始前先拉取。
- 结束后及时提交并推送。
- 如果不同电脑产生冲突，优先保留双方的研究记录，再人工整理。
- 不要把聊天记录当作唯一记忆，重要内容必须进入项目文件。

## 8. 当前推荐流程

策略讨论阶段：

```text
讨论策略
→ 更新 PROJECT_MEMORY.md
→ commit
```

研究执行阶段：

```text
更新市场仓位
→ 更新主线研究
→ 更新 ETF/个股档案
→ 生成操作建议
→ 写入决策日志
→ commit
```

盘后复盘阶段：

```text
记录实际市场表现
→ 对比盘前判断
→ 记录操作是否执行
→ 标记判断偏差
→ 必要时修正规则
→ commit
```
