"""Validation: promote CandidateFact -> ValidatedObservation, or flag for human review.

Every candidate is checked for: traceable provenance, resolvable terminology,
permitted unit, plausible value range, and a non-ambiguous date. Anything that
fails is flagged rather than silently discarded or accepted - a system that
guesses is worse than one that says "uncertain".
"""

from __future__ import annotations

from .terminology import canonicalize_value, is_permitted_unit, normalize_code
from .types import CandidateFact, ValidatedObservation

# Plausible physiological ranges (symbolic; confirm with a clinical advisor).
_PLAUSIBLE: dict[str, tuple[float, float]] = {
    "HBA1C": (3.5, 20.0),      # %, post-canonicalization
    "LDL_CHOL": (10, 500),     # mg/dL
    "HDL_CHOL": (5, 200),
    "CREATININE": (0.1, 20.0), # mg/dL
    "SBP": (50, 260),
    "DBP": (25, 160),
    "POTASSIUM": (1.5, 10.0),
    "SODIUM": (100, 200),
}


def validate(candidate: CandidateFact) -> ValidatedObservation:
    code = normalize_code(candidate.code) if candidate.code else None

    if not candidate.provenance.is_traceable():
        return _flag(candidate, code, "fact is not traceable to a source quote")

    if code is None:
        return _flag(candidate, code, "terminology could not be mapped")

    if candidate.unit and not is_permitted_unit(code, candidate.unit):
        return _flag(candidate, code, f"unit {candidate.unit!r} not permitted for {code}")

    value = candidate.value_numeric
    if value is not None:
        try:
            value, canon_unit = canonicalize_value(code, value, candidate.unit or "%")
        except ValueError as exc:
            return _flag(candidate, code, str(exc))
        lo, hi = _PLAUSIBLE.get(code, (-1e9, 1e9))
        if not (lo <= value <= hi):
            return _flag(candidate, code, f"value {value} outside plausible range for {code}")
    else:
        canon_unit = candidate.unit

    if candidate.ambiguous or candidate.observed_at is None:
        return ValidatedObservation(
            code=code, observed_at=candidate.observed_at, value_numeric=value,
            value_text=candidate.value_text, unit=canon_unit,
            provenance=candidate.provenance, status="flagged",
            reason="date is missing or ambiguous; needs human confirmation")

    return ValidatedObservation(
        code=code, observed_at=candidate.observed_at, value_numeric=value,
        value_text=candidate.value_text, unit=canon_unit,
        provenance=candidate.provenance, status="validated")


def _flag(candidate: CandidateFact, code: str | None, reason: str) -> ValidatedObservation:
    return ValidatedObservation(
        code=code or "UNMAPPED", observed_at=candidate.observed_at,
        value_numeric=candidate.value_numeric, value_text=candidate.value_text,
        unit=candidate.unit, provenance=candidate.provenance,
        status="flagged", reason=reason)
