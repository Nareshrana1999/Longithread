"""Feature engineering from longitudinal observations.

Kept explicit and auditable: a fixed feature list, each with a documented meaning
and unit. The risk model only ever sees these standardized numbers; whatever it
says must be traceable back to the observations that produced them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

FEATURE_NAMES = [
    "hba1c_pct",              # latest HbA1c, % (NGSP)
    "hba1c_slope_pct_per_month",  # linear trend over available history
    "years_since_hba1c",      # staleness of monitoring
    "sbp",                    # latest systolic BP, mmHg
    "dbp",                    # latest diastolic BP, mmHg
    "creatinine_mgdl",        # latest serum creatinine, mg/dL
]


@dataclass
class PatientSignals:
    hba1c: float | None = None
    hba1c_slope: float = 0.0
    years_since_hba1c: float | None = None
    sbp: float | None = None
    dbp: float | None = None
    creatinine: float | None = None

    def is_sufficient(self) -> bool:
        # Minimum evidence to score at all; otherwise abstain for human review.
        return self.hba1c is not None and self.sbp is not None and self.years_since_hba1c is not None

    def to_vector(self) -> list[float]:
        return [
            self.hba1c or 0.0,
            self.hba1c_slope,
            self.years_since_hba1c or 0.0,
            self.sbp or 0.0,
            self.dbp or 0.0,
            self.creatinine or 0.0,
        ]


def build_signals(observations, as_of: datetime) -> PatientSignals:
    """observations: iterable exposing .code, .observed_at, .value_numeric
    (ValidatedObservation or the ORM model)."""
    series: dict[str, list[tuple[datetime, float]]] = {}
    for o in observations:
        if o.value_numeric is None or o.observed_at is None:
            continue
        series.setdefault(o.code, []).append((o.observed_at, o.value_numeric))
    for lst in series.values():
        lst.sort(key=lambda t: t[0])

    def latest(code: str) -> float | None:
        return series[code][-1][1] if series.get(code) else None

    sig = PatientSignals(
        hba1c=latest("HBA1C"),
        sbp=latest("SBP"),
        dbp=latest("DBP"),
        creatinine=latest("CREATININE"),
    )

    h = series.get("HBA1C", [])
    if h:
        sig.years_since_hba1c = max(0.0, (as_of - h[-1][0]).days / 365.0)
        if len(h) >= 2:
            first, last = h[0], h[-1]
            months = max(1e-6, (last[0] - first[0]).days / 30.0)
            sig.hba1c_slope = (last[1] - first[1]) / months
    return sig
