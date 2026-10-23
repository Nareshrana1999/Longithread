"""Patient deterioration-risk scorer (decision support only).

Produces a probability, a coarse band, the top contributing factors, the source
documents behind each factor, and a clear 'for clinician review' recommendation.
It NEVER diagnoses, NEVER changes treatment, and abstains when evidence is thin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .dataset import train_and_evaluate
from .features import PatientSignals, build_signals
from .model import LogisticRegression

_MODEL: LogisticRegression | None = None
_MODEL_METRICS: dict | None = None


def default_model() -> tuple[LogisticRegression, dict]:
    global _MODEL, _MODEL_METRICS
    if _MODEL is None:
        _MODEL, _MODEL_METRICS = train_and_evaluate()
    return _MODEL, _MODEL_METRICS  # type: ignore[return-value]


@dataclass
class RiskFactor:
    name: str
    value: float
    contribution: float  # standardized value * learned weight (signed)
    source_document_ids: list = field(default_factory=list)


@dataclass
class RiskAssessment:
    patient_scored: bool
    probability: float | None
    band: str | None
    factors: list[RiskFactor]
    recommendation: str
    model_metrics: dict | None = None
    abstain_reason: str | None = None

    @classmethod
    def abstain(cls, reason: str, metrics: dict) -> "RiskAssessment":
        return cls(False, None, None, [],
                   "Insufficient reliable data to score this patient. "
                   "Route to a clinician for manual review.",
                   model_metrics=metrics, abstain_reason=reason)


def _raw_values(sig: PatientSignals) -> dict[str, float]:
    return {
        "hba1c_pct": sig.hba1c or 0.0,
        "hba1c_slope_pct_per_month": sig.hba1c_slope,
        "years_since_hba1c": sig.years_since_hba1c or 0.0,
        "sbp": sig.sbp or 0.0,
        "dbp": sig.dbp or 0.0,
        "creatinine_mgdl": sig.creatinine or 0.0,
    }


def _sources_for(observations) -> dict[str, list]:
    out: dict[str, list] = {}
    for o in observations:
        doc = getattr(o.provenance, "source_document_id", None) if hasattr(o, "provenance") \
            else getattr(o, "source_document_id", None)
        if doc is not None:
            out.setdefault(o.code, []).append(str(doc))
    return out


def _band(p: float) -> str:
    return "high" if p >= 0.5 else "moderate" if p >= 0.2 else "low"


def score_patient(observations, as_of: datetime | None = None) -> RiskAssessment:
    as_of = as_of or datetime.now()
    model, metrics = default_model()
    sig = build_signals(observations, as_of)
    if not sig.is_sufficient():
        return RiskAssessment.abstain("missing HbA1c or blood-pressure evidence", metrics)

    vec = sig.to_vector()
    prob = model.predict_proba(vec)
    contribs = [w * ((v - m) / (s or 1.0))
                for w, v, m, s in zip(model.weights, vec, model.means, model.stds)]
    raw = _raw_values(sig)
    src = _sources_for(observations)
    name_to_code = {"hba1c_pct": "HBA1C", "hba1c_slope_pct_per_month": "HBA1C",
                    "years_since_hba1c": "HBA1C", "sbp": "SBP", "dbp": "DBP",
                    "creatinine_mgdl": "CREATININE"}
    factors = sorted(
        [RiskFactor(name=n, value=round(raw[n], 4), contribution=round(c, 4),
                    source_document_ids=sorted(set(src.get(name_to_code[n], []))))
         for n, c in zip(model.features, contribs)],
        key=lambda f: abs(f.contribution), reverse=True)

    band = _band(prob)
    rec = ("Elevated composite deterioration signal - recommend clinician review of "
           "control and monitoring cadence." if band in {"high", "moderate"} else
           "No elevated composite signal; continue standard protocol follow-up.")
    return RiskAssessment(True, round(prob, 3), band, factors, rec, model_metrics=metrics)
