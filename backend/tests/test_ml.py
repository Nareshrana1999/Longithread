from datetime import datetime, timedelta

from app.ml.dataset import train_and_evaluate
from app.ml.features import PatientSignals, build_signals
from app.ml.model import roc_auc, sigmoid
from app.ml.risk import score_patient


class _Prov:
    def __init__(self, doc): self.source_document_id = doc


class _Obs:
    def __init__(self, code, when, val, doc):
        self.code, self.observed_at, self.value_numeric, self.status = code, when, val, "validated"
        self.provenance = _Prov(doc)


def test_sigmoid_bounds():
    assert sigmoid(-100) < 1e-3 and sigmoid(100) > 0.999


def test_auc_perfect_ranking():
    assert abs(roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) - 1.0) < 1e-9


def test_baseline_model_learns():
    _, m = train_and_evaluate()
    assert m["auc"] >= 0.75, m
    assert m["brier"] <= 0.20, m
    assert m["precision"] >= 0.7 and m["recall"] >= 0.7, m


def test_high_risk_patient_scores_high_with_attribution():
    now = datetime(2024, 7, 15)
    obs = [
        _Obs("HBA1C", now - timedelta(days=15), 11.0, "d1"),
        _Obs("SBP", now - timedelta(days=15), 170, "d2"),
        _Obs("DBP", now - timedelta(days=15), 105, "d2"),
        _Obs("CREATININE", now - timedelta(days=15), 2.1, "d3"),
    ]
    r = score_patient(obs, as_of=now)
    assert r.patient_scored and r.band == "high"
    assert r.factors[0].contribution != 0
    # every HbA1c-derived factor carries provenance
    hb = [f for f in r.factors if f.name.startswith("hba1c")]
    assert hb and all(f.source_document_ids for f in hb)


def test_abstains_on_insufficient_data():
    r = score_patient([_Obs("LDL_CHOL", datetime(2024, 5, 1), 130, "d1")], as_of=datetime(2024, 6, 1))
    assert not r.patient_scored
    assert r.abstain_reason and "clinician" in r.recommendation.lower()


def test_build_signals_slope_and_staleness():
    obs = [_Obs("HBA1C", datetime(2024, 1, 1), 7.0, "a"), _Obs("HBA1C", datetime(2024, 6, 1), 9.0, "b")]
    sig = build_signals(obs, datetime(2024, 6, 1))
    assert abs(sig.hba1c_slope - (2.0 / 5)) < 0.05  # +2% over ~5 months
    assert sig.years_since_hba1c < 0.01
