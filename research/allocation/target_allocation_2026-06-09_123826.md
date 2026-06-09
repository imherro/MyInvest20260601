# Target Allocation

Generated at: 2026-06-09_123826
Basis trade date: 20260608

## Summary

Market score 25 maps to equity 30%-40% and cash/short-duration 60%-70%; actual equity is about 46.93%, so downstream action plans may only reduce risk unless upstream gates improve.

| Item | Target |
| --- | ---: |
| Equity | 30%-40%, center 35% |
| Cash/short-duration | 60%-70%, center 65% |
| Offensive bucket | pause_new |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 53.04% | -11.96pp |
| 宽基/核心底仓 | 19.95% | 7.81% | -12.14pp |
| 进攻主线仓 | 4.90% | 9.61% | +4.71pp |
| 防御仓 | 10.15% | 15.96% | +5.81pp |
| 其他/待清理 | 0.00% | 13.55% | +13.55pp |

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
| 现金/短融 | 53.04% | 65.00% | P0 |
| 宽基/核心底仓 | 7.81% | 19.95% | Observe |
| 进攻主线仓 | 9.61% | 4.90% | P1 |
| 防御仓 | 15.96% | 10.15% | P1 |
| 其他/待清理 | 13.55% | 0.00% | P0 |

## Constraints

- This module does not generate buy/sell instructions.
- Core underweight does not justify adding while total equity is above target.
- Offensive add actions are blocked when offensive_bucket_status is pause_new.

## Quality

Status: warning

- QMT open_price/cost field is non-positive; cost-based PnL is unavailable, but ratio-level portfolio analysis can continue.
