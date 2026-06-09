# Target Allocation

Generated at: 2026-06-09_150100
Basis trade date: 20260608

## Summary

Market score 25 maps to equity 30%-40% and cash/short-duration 60%-70%; actual equity is about 0.00%, so downstream action plans may only reduce risk unless upstream gates improve.

| Item | Target |
| --- | ---: |
| Equity | 30%-40%, center 35% |
| Cash/short-duration | 60%-70%, center 65% |
| Offensive bucket | pause_new |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 0.00% | -65.00pp |
| 宽基/核心质量底仓 | 19.95% | 0.00% | -19.95pp |
| 进攻主线仓 | 4.90% | 0.00% | -4.90pp |
| 防御仓 | 10.15% | 0.00% | -10.15pp |

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
| 现金/短融 | 0.00% | 65.00% | P0 |
| 宽基/核心质量底仓 | 0.00% | 19.95% | Observe |
| 进攻主线仓 | 0.00% | 4.90% | Observe |
| 防御仓 | 0.00% | 10.15% | Observe |

## Constraints

- This module does not generate buy/sell instructions.
- Core underweight does not justify adding while total equity is above target.
- Offensive add actions are blocked when offensive_bucket_status is pause_new.

## Quality

Status: ok

- no major warning
