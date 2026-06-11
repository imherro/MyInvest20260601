# Target Allocation

Generated at: 2026-06-11_111812
Basis trade date: 20260608

## Summary

Market score 25 maps to equity 30%-40% and cash/short-duration 60%-70%; actual equity is about 43.03%, so downstream action plans may only reduce risk unless upstream gates improve.

| Item | Target |
| --- | ---: |
| Equity | 30%-40%, center 35% |
| Cash/short-duration | 60%-70%, center 65% |
| Offensive bucket | pause_new |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 57.03% | -7.97pp |
| 宽基底仓 | 19.95% | 1.33% | -18.62pp |
| 进攻主线仓 | 4.90% | 11.94% | +7.04pp |
| 防御仓 | 10.15% | 17.61% | +7.46pp |
| 其他/待清理 | 0.00% | 12.16% | +12.16pp |

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
| 现金/短融 | 57.03% | 65.00% | P0 |
| 宽基底仓 | 1.33% | 19.95% | Observe |
| 进攻主线仓 | 11.94% | 4.90% | P1 |
| 防御仓 | 17.61% | 10.15% | P1 |
| 其他/待清理 | 12.16% | 0.00% | P0 |

## Constraints

- This module does not generate buy/sell instructions.
- Core underweight does not justify adding while total equity is above target.
- Offensive add actions are blocked when offensive_bucket_status is pause_new.

## Quality

Status: ok

- no major warning
