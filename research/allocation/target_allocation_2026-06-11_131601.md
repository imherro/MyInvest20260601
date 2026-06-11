# Target Allocation

Generated at: 2026-06-11_131601
Basis trade date: 20260608

## Summary

Market score 25 maps to equity 30%-40% and cash/short-duration 60%-70%; actual equity is about 43.09%, so downstream action plans may only reduce risk unless upstream gates improve.

| Item | Target |
| --- | ---: |
| Equity | 30%-40%, center 35% |
| Cash/short-duration | 60%-70%, center 65% |
| Offensive bucket | pause_new |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 56.91% | -8.09pp |
| 宽基底仓 | 19.95% | 1.33% | -18.62pp |
| 进攻主线仓 | 4.90% | 11.94% | +7.04pp |
| 防御仓 | 10.15% | 17.63% | +7.48pp |
| 其他/待清理 | 0.00% | 12.18% | +12.18pp |

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
| 现金/短融 | 56.91% | 65.00% | P0 |
| 宽基底仓 | 1.33% | 19.95% | Observe |
| 进攻主线仓 | 11.94% | 4.90% | P1 |
| 防御仓 | 17.63% | 10.15% | P1 |
| 其他/待清理 | 12.18% | 0.00% | P0 |

## Constraints

- This module does not generate buy/sell instructions.
- Core underweight does not justify adding while total equity is above target.
- Offensive add actions are blocked when offensive_bucket_status is pause_new.

## Quality

Status: ok

- no major warning
