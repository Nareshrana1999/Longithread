from datetime import datetime

from app.clinical.pipeline import run_pipeline
import uuid

REF = datetime(2024, 6, 1)


def _obs(text):
    return run_pipeline([(uuid.uuid4(), text, REF)])


def test_contradictory_same_date_values_conflict():
    r = run_pipeline([
        (uuid.uuid4(), "LDL cholesterol 90 mg/dL 2024-05-20", REF),
        (uuid.uuid4(), "LDL cholesterol 220 mg/dL 2024-05-20", REF),
    ])
    assert r.conflicts, "expected a conflict between contradictory LDL values"
    # and it must NOT silently pick one - both become flagged
    assert all(o.status == "flagged" for o in r.observations)


def test_matching_representations_do_not_conflict():
    r = run_pipeline([
        (uuid.uuid4(), "HbA1c 58 mmol/mol 2024-05-20", REF),
        (uuid.uuid4(), "HbA1c 7.4 % 2024-05-20", REF),
    ])
    assert not r.conflicts


def test_conflicting_medication_lists_detected():
    r = run_pipeline([
        (uuid.uuid4(), "Medication list 2024-05-01: Metformin", REF),
        (uuid.uuid4(), "Medication list 2024-05-01: Insulin glargine", REF),
    ])
    assert any(c.code == "MED_LIST" for c in r.conflicts)
