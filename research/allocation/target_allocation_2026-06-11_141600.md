# Target Allocation

Generated at: 2026-06-11_141600
Basis trade date: 20260610

## Summary

Market score 25 maps to equity 30%-40% and cash/short-duration 60%-70%; actual equity is about 43.02%, so downstream action plans may only reduce risk unless upstream gates improve.

| Item | Target |
| --- | ---: |
| Equity | 30%-40%, center 35% |
| Cash/short-duration | 60%-70%, center 65% |
| Offensive bucket | pause_new |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 56.98% | -8.02pp |
| 宽基底仓 | 19.95% | 1.33% | -18.62pp |
| 进攻主线仓 | 4.90% | 11.88% | +6.98pp |
| 防御仓 | 10.15% | 17.66% | +7.51pp |
| 其他/待清理 | 0.00% | 12.15% | +12.15pp |

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
| 现金/短融 | 56.98% | 65.00% | P0 |
| 宽基底仓 | 1.33% | 19.95% | Observe |
| 进攻主线仓 | 11.88% | 4.90% | P1 |
| 防御仓 | 17.66% | 10.15% | P1 |
| 其他/待清理 | 12.15% | 0.00% | P0 |

## Constraints

- This module does not generate buy/sell instructions.
- Core underweight does not justify adding while total equity is above target.
- Offensive add actions are blocked when offensive_bucket_status is pause_new.

## Quality

Status: ok

- no major warning
