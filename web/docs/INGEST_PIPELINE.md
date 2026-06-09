# Ingest Pipeline

Input:

```text
research/latest_index.json -> modules
```

Pipeline:

1. Read `research/latest_index.json`.
2. Resolve only `latest_index.modules`.
3. Run existing project checks.
4. Load current action plan, target allocation, intraday rules, portfolio snapshot, market score, market-position mapping, bucket registry, liquidity gate registry, 511360 profile, 511360 valuation, and decision log headings.
5. Sanitize all persisted fields.
6. Rebuild `temp/web_db/myinvest.sqlite`.
7. Verify every database row with `RatioOnlyService`.

The pipeline never reads `latest_index.files` as current state.

The Web review-package export also resolves source files through `current_modules` and does not use `latest_index.files` as current state.
