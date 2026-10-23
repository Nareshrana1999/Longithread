from datetime import datetime

from app.clinical.pipeline import run_pipeline
from app.rules.engine import PROTOCOLS, evaluate
import uuid

AS_OF = datetime(2024, 6, 15)
REF = datetime(2024, 6, 1)


def _validated(texts):
    r = run_pipeline([(uuid.uuid4(), t, REF) for t in texts])
    return [o for o in r.validated if o.observed_at]


def _states(texts):
    obs = _validated(texts)
    sug = evaluate(PROTOCOLS["diabetes_v1"], obs, AS_OF)
    return {s.rule_id: s.state for s in sug}


def test_overdue_hba1c_is_due():
    assert _states(["HbA1c 60 mmol/mol 2024-01-10"])["R-HBA1C-Q3M"] == "due"


def test_recent_hba1c_is_not_due():
    assert _states(["HbA1c 60 mmol/mol 2024-06-01"])["R-HBA1C-Q3M"] == "not_due"


def test_absent_record_is_record_missing_not_never_done():
    # The blueprint's key distinction: no creatinine in the record must NOT be
    # reported as "test never performed" nor auto-create a task.
    assert _states(["HbA1c 50 mmol/mol 2024-06-01"])["R-CREAT-Y1"] == "RECORD_MISSING"
