"""Cohort-level data analysis for care teams.

Aggregates workflow performance (follow-up completion, overdue load, review rates),
monitoring gaps, and simple population trends. Everything is derived from
validated observations and clinician-reviewed tasks so numbers are traceable to
the same provenance the rest of the system demands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.ml.features import build_signals


@dataclass
class CohortSummary:
    n_patients: int
    tasks_created: int
    tasks_pending: int
    tasks_overdue: int
    tasks_reviewed: int
    completion_rate: float
    review_rate: float
    monitoring_gap_rate: float
    mean_latest_hba1c: float | None
    mean_hba1c_slope_per_month: float | None
    by_condition: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "n_patients": self.n_patients,
            "tasks_created": self.tasks_created,
            "tasks_pending": self.tasks_pending,
            "tasks_overdue": self.tasks_overdue,
            "tasks_reviewed": self.tasks_reviewed,
            "completion_rate": round(self.completion_rate, 4),
            "review_rate": round(self.review_rate, 4),
            "monitoring_gap_rate": round(self.monitoring_gap_rate, 4),
            "mean_latest_hba1c": self.mean_latest_hba1c,
            "mean_hba1c_slope_per_month": self.mean_hba1c_slope_per_month,
            "by_condition": self.by_condition,
        }


def summarize_cohort(patients: list[dict], as_of: datetime | None = None) -> CohortSummary:
    """patients: list of {'condition': str, 'observations': [...], 'tasks': [...]}."""
    as_of = as_of or datetime.now()
    total = created = pending = overdue = reviewed = 0
    cond: dict[str, dict] = {}
    hba1c_lates, slopes = [], []
    gap_patients = 0

    for rec in patients:
        total += 1
        tasks = rec.get("tasks", [])
        obs = rec.get("observations", [])
        c = created + len(tasks)
        created = c
        for t in tasks:
            st = t.status
            if st == "pending":
                pending += 1
                if getattr(t, "due_at", None) and t.due_at < as_of:
                    overdue += 1
            if st in {"accepted", "done", "rejected"}:
                reviewed += 1

        condition = rec.get("condition") or "unspecified"
        bucket = cond.setdefault(condition, {"patients": 0, "overdue": 0, "tasks": 0, "done": 0})
        bucket["patients"] += 1
        bucket["tasks"] += len(tasks)
        bucket["overdue"] += sum(1 for t in tasks if t.status == "pending"
                                 and getattr(t, "due_at", None) and t.due_at < as_of)
        bucket["done"] += sum(1 for t in tasks if t.status in {"accepted", "done"})

        # monitoring gap: no HbA1c in the last 12 months
        sig = build_signals(obs, as_of)
        has_recent = (sig.hba1c is not None and sig.years_since_hba1c is not None
                      and sig.years_since_hba1c * 365 <= 365)
        if not has_recent:
            gap_patients += 1
        if sig.hba1c is not None:
            hba1c_lates.append(sig.hba1c)
        if len([o for o in obs if o.code == "HBA1C"]) >= 2:
            slopes.append(sig.hba1c_slope)

    completion = (sum(b["done"] for b in cond.values()) / created) if created else 0.0

    by_condition = {
        k: {
            "patients": v["patients"],
            "tasks": v["tasks"],
            "overdue": v["overdue"],
            "done": v["done"],
            "completion_rate": round(v["done"] / v["tasks"], 4) if v["tasks"] else 0.0,
        }
        for k, v in cond.items()
    }

    return CohortSummary(
        n_patients=total,
        tasks_created=created,
        tasks_pending=pending,
        tasks_overdue=overdue,
        tasks_reviewed=reviewed,
        completion_rate=completion,
        review_rate=(reviewed / created) if created else 0.0,
        monitoring_gap_rate=(gap_patients / total) if total else 0.0,
        mean_latest_hba1c=round(sum(hba1c_lates) / len(hba1c_lates), 2) if hba1c_lates else None,
        mean_hba1c_slope_per_month=round(sum(slopes) / len(slopes), 4) if slopes else None,
        by_condition=by_condition,
    )
