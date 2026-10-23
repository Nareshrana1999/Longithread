"""Clinician-approved, versioned follow-up rules.

A rule does NOT decide treatment. It only says, given validated observations,
whether a scheduled follow-up is due. Versioning + explicit rule ids make every
suggestion auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CareRule:
    rule_id: str
    version: str
    name: str
    code: str               # required observation code
    interval_days: int      # how often the item must be done
    indication: str         # e.g. diabetes, hypertension

    @classmethod
    def from_config(cls, cfg: dict) -> "CareRule":
        return cls(**cfg)


# Bundled protocol. Ship as data so a clinical advisor can edit/approve it.
DIABETES_CARE_V1 = [
    CareRule("R-HBA1C-Q3M", "1.0", "Quarterly HbA1c", "HBA1C", 90, "diabetes"),
    CareRule("R-LDL-Y1", "1.0", "Annual lipid panel", "LDL_CHOL", 365, "diabetes"),
    CareRule("R-CREAT-Y1", "1.0", "Annual kidney function", "CREATININE", 365, "diabetes"),
]
HYPERTENSION_CARE_V1 = [
    CareRule("R-SBP-Q3M", "1.0", "Quarterly BP", "SBP", 90, "hypertension"),
]
HYPERTENSION_CARE_V2 = [
    CareRule("R-SBP-Q3M", "2.0", "Quarterly BP", "SBP", 90, "hypertension"),
    CareRule("R-DBP-Q3M", "2.0", "Quarterly diastolic BP", "DBP", 90, "hypertension"),
    CareRule("R-POTASSIUM-Y1", "2.0", "Annual potassium (RAAS agents)", "POTASSIUM", 365, "hypertension"),
]
CKD_CARE_V1 = [
    CareRule("R-CREAT-Q6M", "1.0", "6-monthly kidney function", "CREATININE", 182, "ckd"),
    CareRule("R-POTASSIUM-Q6M", "1.0", "6-monthly potassium", "POTASSIUM", 182, "ckd"),
]
CHRONIC_COMBINED_V1 = [
    CareRule("R-HBA1C-Q3M", "1.0", "Quarterly HbA1c", "HBA1C", 90, "diabetes"),
    CareRule("R-LDL-Y1", "1.0", "Annual lipid panel", "LDL_CHOL", 365, "diabetes"),
    CareRule("R-SBP-Q3M", "1.0", "Quarterly BP", "SBP", 90, "hypertension"),
    CareRule("R-CREAT-Y1", "1.0", "Annual kidney function", "CREATININE", 365, "ckd"),
]
PROTOCOLS: dict[str, list[CareRule]] = {
    "diabetes_v1": DIABETES_CARE_V1,
    "hypertension_v1": HYPERTENSION_CARE_V1,
    "hypertension_v2": HYPERTENSION_CARE_V2,
    "ckd_v1": CKD_CARE_V1,
    "chronic_combined_v1": CHRONIC_COMBINED_V1,
}


@dataclass
class TaskSuggestion:
    rule_id: str
    rule_version: str
    name: str
    state: str              # due | not_due | RECORD_MISSING
    due_at: datetime | None
    rationale: str


def evaluate(rules: list[CareRule], observations, as_of: datetime) -> list[TaskSuggestion]:
    """observations: iterable of objects exposing .code and .observed_at
    (ValidatedObservation or the ORM model - both work)."""
    # latest validated observation per code
    latest: dict[str, datetime] = {}
    for obs in observations:
        when = obs.observed_at
        if when is None:
            continue
        cur = latest.get(obs.code)
        if cur is None or when > cur:
            latest[obs.code] = when

    suggestions: list[TaskSuggestion] = []
    for rule in rules:
        last = latest.get(rule.code)
        if last is None:
            # Safety property: absence of a record is NOT the same as "never done".
            suggestions.append(TaskSuggestion(
                rule_id=rule.rule_id, rule_version=rule.version, name=rule.name,
                state="RECORD_MISSING", due_at=None,
                rationale=f"No {rule.code} in the record. Cannot confirm whether it was "
                          f"never performed or simply missing/unlinked. Needs verification."))
            continue
        due_at = last + timedelta(days=rule.interval_days)
        if due_at <= as_of:
            suggestions.append(TaskSuggestion(
                rule_id=rule.rule_id, rule_version=rule.version, name=rule.name,
                state="due", due_at=due_at,
                rationale=f"Last {rule.code} on {last.date()}; interval {rule.interval_days}d elapsed."))
        else:
            suggestions.append(TaskSuggestion(
                rule_id=rule.rule_id, rule_version=rule.version, name=rule.name,
                state="not_due", due_at=due_at,
                rationale=f"Next {rule.code} not due until {due_at.date()}."))
    return suggestions
