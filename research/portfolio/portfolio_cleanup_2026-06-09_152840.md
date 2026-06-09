# Portfolio Cleanup Review: 2026-06-09_152840

Boundary: ratio-only portfolio review. No single-security buy/sell/add/reduce instruction.

## Bucket Deviation

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
| 现金/短融 | 65.00% | 56.48% | -8.52pp |
| 宽基底仓 | 19.95% | 1.34% | -18.61pp |
| 进攻主线仓 | 4.90% | 12.43% | +7.53pp |
| 防御仓 | 10.15% | 17.46% | +7.31pp |
| 其他/待清理 | 0.00% | 12.28% | +12.28pp |

## Cleanup Priorities

| Priority | Bucket | Issue | Gap | Principle |
| --- | --- | --- | ---: | --- |
| P1 | 现金/短融 | cash_short_below_target | -8.52pp | restore only paired with equity risk reduction |
| P3 | 进攻主线仓 | equity_bucket_above_target | +7.53pp | no new adds while market gate is risk-off |
| P3 | 防御仓 | equity_bucket_above_target | +7.31pp | no new adds while market gate is risk-off |
| P2 | 其他/待清理 | legacy_watch_above_target | +12.28pp | compress legacy/watch before considering equity adds |

## Boundaries
- No single-security buy/sell/add/reduce instruction.
- Use percentage points and bucket deviations only.
- Regenerate a portfolio snapshot after execution.
