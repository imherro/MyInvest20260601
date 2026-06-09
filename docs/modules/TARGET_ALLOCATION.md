# 理想仓位参考模块

## 职责

理想仓位参考模块用于给出当前市场环境下的目标仓位中枢，并作为真实持仓的对照基准。

它不直接生成买卖指令。买卖动作仍由操作建议模块生成，并且必须引用市场仓位、主题研究、ETF/个股档案、组合分析和本模块的偏离结果。

## 输入

- 最新市场仓位报告
- 最新主题研究报告
- 必要的盘后公开行情核对
- 可选：最新真实持仓快照，仅用于计算偏离覆盖层，不得用于决定理想仓位结构

## 输出

- 总权益仓目标
- 现金短融桶目标
- 分组理想仓位
- 实际仓位与理想仓位的偏离
- 偏离优先级
- 约束规则
- 盘中作战地图可直接消费的 `ideal_allocation_map`

`ideal_allocation_map` 必须先由市场仓位、主题强度和配置约束生成，不受真实持仓影响。真实持仓只能作为 `actual_allocation_overlay` 与理想结构对照。

建议 JSON 字段：

```json
{
  "ideal_allocation_map": {
    "basis": "market_position_and_theme_analysis",
    "segments": [
      {"key": "cash_short", "label": "现金/短融", "target_pct": 0},
      {"key": "core_base", "label": "宽基底仓", "target_pct": 0},
      {"key": "attack_mainline", "label": "进攻主线仓", "target_pct": 0},
      {"key": "defense", "label": "防御仓", "target_pct": 0}
    ]
  }
}
```

如果该字段缺失，盘中规则生成器可以临时从 `target_allocation.groups` 降级映射，但必须在 `intraday_rules.json` 记录 `missing_upstream`，提醒本模块补齐。

## 文件命名

```text
research/allocation/target_allocation_YYYY-MM-DD_HHMMSS.md
research/allocation/target_allocation_YYYY-MM-DD_HHMMSS.json
```

## 禁止事项

- 不直接给出具体买卖动作。
- 不用单日行情替代市场仓位模块。
- 不因为某组低配就自动加仓。
- 不绕过 ETF/个股档案处理单个标的。
- 不让真实持仓决定理想仓位桶；真实持仓只参与偏离显示。
