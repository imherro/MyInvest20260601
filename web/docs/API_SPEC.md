# Web API Spec

All endpoints are read-only and return:

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "errors": [],
  "source": {}
}
```

Endpoints:

- `GET /api/health`
- `GET /api/current`
- `GET /api/latest-index`
- `GET /api/action-plan/current`
- `GET /api/target-allocation/current`
- `GET /api/research-first/current`
- `GET /api/portfolio/current`
- `GET /api/intraday-rules/current`
- `GET /api/system-check/current`
- `GET /api/decision-log/current`
- `GET /api/allocation-consistency/current`

All responses pass `RatioOnlyService` before returning. A sanitizer failure returns HTTP 500.
