# Target Allocation

Generated at: 2026-06-09_150300
Basis trade date: 20260608

## Summary

Market score 25 maps to equity 30%-40% and cash/short-duration 60%-70%; actual equity is about 43.52%, so downstream action plans may only reduce risk unless upstream gates improve.

| Item | Target |
| --- | ---: |
| Equity | 30%-40%, center 35% |
| Cash/short-duration | 60%-70%, center 65% |
| Offensive bucket | pause_new |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 56.48% | -8.52pp |
| 宽基/核心质量底仓 | 19.95% | 7.80% | -12.15pp |
| 进攻主线仓 | 4.90% | 9.04% | +4.14pp |
| 防御仓 | 10.15% | 12.99% | +2.84pp |
| 其他/待清理 | 0.00% | 13.69% | +13.69pp |

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
| 现金/短融 | 56.48% | 65.00% | P0 |
| 宽基/核心质量底仓 | 7.80% | 19.95% | Observe |
| 进攻主线仓 | 9.04% | 4.90% | P1 |
| 防御仓 | 12.99% | 10.15% | P1 |
| 其他/待清理 | 13.69% | 0.00% | P0 |

## Constraints

- This module does not generate buy/sell instructions.
- Core underweight does not justify adding while total equity is above target.
- Offensive add actions are blocked when offensive_bucket_status is pause_new.

## Quality

Status: ok

- no major warning
