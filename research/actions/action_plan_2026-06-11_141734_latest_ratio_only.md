# Ratio-Only Action Plan

Generated at: 2026-06-11_141734
Basis trade date: 20260610

## Summary

Target equity is 30%-40%; actual equity is about 43.02%. Allowed actions are ratio-only risk reduction and cash/short-duration restoration; no direct single-name add is allowed without fresh dossiers.

## Actions

| Priority | Action | Subject | Current | Suggested change | Target |
| --- | --- | --- | ---: | ---: | ---: |
| high | Reduce | overall equity exposure | 43.02% | reduce 3.0pp to 8.0pp | 30%-40% |
| high | Add | cash/short-duration bucket | 56.98% | increase 3.0pp to 8.0pp | 60%-70% |
| high | Reduce | 其他/待清理 | 12.15% | reduce in stages before considering core adds | 0.00% |

## No Action

| Subject | Reason | Watch points |
| --- | --- | --- |
| core_base bucket | underweight is not an add signal while overall equity is above target | wait for market score or target range improvement |
| attack_mainline bucket | offensive gate is controlled by market/theme status | actual 11.88%; no new attack exposure while pause_new |
| defense bucket | defensive equity is still equity exposure | actual 17.66%; do not treat defense bucket as cash |

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

- `research/market/market_score_2026-06-11_140751.json`
- `research/themes/theme_review_2026-06-08_102237.json`
- `research/portfolio/portfolio_snapshot_2026-06-11_141600.json`
- `research/allocation/target_allocation_2026-06-11_141652.json`
- `research/alerts/intraday_rules.json`
