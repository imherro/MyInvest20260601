# Ratio-Only Action Plan

Generated at: 2026-06-09_154226
Basis trade date: 20260608

## Summary

Target equity is 30%-40%; actual equity is about 43.52%. Allowed actions are ratio-only risk reduction and cash/short-duration restoration; no direct single-name add is allowed without fresh dossiers.

## Actions

| Priority | Action | Subject | Current | Suggested change | Target |
| --- | --- | --- | ---: | ---: | ---: |
| high | Reduce | overall equity exposure | 43.52% | reduce 3.5pp to 8.5pp | 30%-40% |
| high | Add | cash/short-duration bucket | 56.48% | increase 3.5pp to 8.5pp | 60%-70% |
| high | Reduce | 其他/待清理 | 12.28% | reduce in stages before considering core adds | 0.00% |

## No Action

| Subject | Reason | Watch points |
| --- | --- | --- |
| core_base bucket | underweight is not an add signal while overall equity is above target | wait for market score or target range improvement |
| attack_mainline bucket | offensive gate is controlled by market/theme status | actual 12.43%; no new attack exposure while pause_new |
| defense bucket | defensive equity is still equity exposure | actual 17.46%; do not treat defense bucket as cash |

## ResearchFirst

| Subject | Missing content | Why blocked | Next step |
| --- | --- | --- | --- |
| - | none | no pending registry item | - |

## Hard Constraints

- No monetary-value fields.
- No unit-count fields.
- No direct buy/add/reduce/sell for ResearchFirst subjects.
- Single-security executable actions require profile, valuation and liquidity gate pass.
- Cash/short-duration actions require liquidity, duration-boundary and interest-rate/credit/liquidity risk checks.

## Risks

- Registry or valuation staleness can only loosen actions after refresh.
- This file is ratio-only and must not be translated into monetary or unit instructions.

## Sources

- `research/market/market_score_2026-06-09_100448.json`
- `research/themes/theme_review_2026-06-08_102237.json`
- `research/portfolio/portfolio_snapshot_2026-06-09_143440.json`
- `research/allocation/target_allocation_2026-06-09_150300.json`
- `research/alerts/intraday_rules.json`
