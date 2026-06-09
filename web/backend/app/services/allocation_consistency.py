from __future__ import annotations

from sqlalchemy.orm import Session

from .current_state import CurrentStateService


class AllocationConsistencyService:
    tolerance_pp = 0.05

    def __init__(self, session: Session):
        self.current = CurrentStateService(session)

    def check(self) -> dict:
        target = self.current.target_allocation() or {}
        intraday = self.current.intraday_rules() or {}
        target_buckets = {item["bucket"]: item for item in target.get("buckets", [])}
        rule_buckets = {item["bucket"]: item for item in intraday.get("buckets", [])}
        mismatches = []
        for key in sorted(set(target_buckets) | set(rule_buckets)):
            left = target_buckets.get(key)
            right = rule_buckets.get(key)
            if not left or not right:
                mismatches.append({"bucket": key, "field": "presence"})
                continue
            for field in ["actual_pct", "target_pct", "gap_pct"]:
                if left.get(field) is None or right.get(field) is None:
                    continue
                if abs(float(left[field]) - float(right[field])) > self.tolerance_pp:
                    mismatches.append({"bucket": key, "field": field, "target": left[field], "intraday": right[field]})
        return {"status": "ok" if not mismatches else "fail", "mismatches": mismatches}
