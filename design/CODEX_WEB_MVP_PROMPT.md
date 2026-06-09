# Codex Prompt - Fix Developer Package Then Build Web MVP

Use this prompt after updating AGENTS.md.

```text
You are working in the MyInvest repository. First, do not build Web code until package preflight issues are fixed.

Step 1: Fix developer package hygiene:
1. Ensure `.env.example` exists with empty placeholders only.
2. Update `research/config/liquidity_gate_registry.json` so `511360.valuation_source` points to an existing packaged valuation file, preferably the latest available 511360 valuation JSON, or include the missing source file.
3. Update developer package manifest logic so it does not hardcode `142000`; current action plan must be resolved from `research/latest_index.json` modules.action_plan.path.
4. Re-run:
   python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>
   python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>
   python scripts/check_cross_file_allocation_consistency.py
   python scripts/project_check.py --current-only
5. Continue only when all blocking checks return OK / 0 FAIL.

Step 2: Create docs if missing:
- docs/WEB_REQUIREMENTS.md
- docs/WEB_ARCHITECTURE.md

Use the provided design docs as the source of truth.

Step 3: Build read-only Web MVP:
- Backend: FastAPI.
- Frontend: React + Ant Design, or FastAPI + Jinja2 if keeping MVP simpler.
- No database in Phase 1.
- No automatic trading.
- Use current-only resolver from research/latest_index.json modules.
- All API responses must pass ratio-only sanitizer.
- API must reject forbidden fields and local absolute paths.
- Implement:
  GET /api/health
  GET /api/latest-index
  GET /api/action-plan/current
  GET /api/target-allocation/current
  GET /api/intraday-rules/current
  GET /api/portfolio/current
  GET /api/research-first/current
  GET /api/system-check/current

Step 4: Add tests:
- tests/test_web_api_ratio_only.py
- tests/test_web_api_current_only.py
- tests/test_web_api_research_first.py

Acceptance:
- check_ratio_only OK
- check_research_first_gate OK
- check_cross_file_allocation_consistency OK
- project_check.py --current-only 0 FAIL
- pytest passes
- No Web API returns monetary amount, share count, account, order, fill, local absolute path, or execution data.
```
