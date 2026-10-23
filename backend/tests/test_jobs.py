import time
import uuid
from datetime import datetime

from tests.conftest import _headers


def _patient(client, tid):
    return client.post("/patients", json={"condition": "diabetes"}, headers=_headers(tid)).json()["id"]


def test_async_import_job_completes(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid)
    body = {"patient_id": pid, "document_type": "lab_report",
            "text": "HbA1c 58 mmol/mol 2024-05-20", "reference_date": str(datetime(2024, 6, 1))}
    r = client.post("/jobs/import", json=body, headers=_headers(tid))
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    status = None
    for _ in range(50):
        j = client.get(f"/jobs/{job_id}", headers=_headers(tid)).json()
        status = j["status"]
        if status in {"done", "error"}:
            break
        time.sleep(0.05)
    assert status == "done", j
    # result should be JSON-safe (uuid was coerced during serialization)
    assert isinstance(j["result"], (dict, list))
    # the import really happened
    assert client.get(f"/patients/{pid}/timeline", headers=_headers(tid)).json()


def test_new_protocols_accepted(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid)
    for proto in ("hypertension_v2", "ckd_v1", "chronic_combined_v1"):
        r = client.post(f"/patients/{pid}/tasks/generate?protocol={proto}", headers=_headers(tid))
        assert r.status_code == 200, proto


def test_ml_model_endpoint_exposes_transparent_metrics(client):
    tid = uuid.uuid4()
    m = client.get("/ml/model", headers=_headers(tid)).json()
    assert m["model"] == "logistic_regression_v1"
    assert m["metrics_on_synthetic_holdout"]["auc"] >= 0.75
    assert m["not_for"]  # decision-support guardrail is surfaced, not hidden


def test_cohort_endpoint_scoped_to_tenant(client):
    ta, tb = uuid.uuid4(), uuid.uuid4()
    _patient(client, ta)
    _patient(client, ta)
    _patient(client, tb)
    assert client.get("/analytics/cohort", headers=_headers(ta)).json()["n_patients"] == 2
    assert client.get("/analytics/cohort", headers=_headers(tb)).json()["n_patients"] == 1


def test_dashboard_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Longithread" in r.text


def test_cohort_aggregates_over_real_orm_rows(client):
    """Regression: /analytics/cohort must work over persisted ORM observations.

    The earlier bug read `.status` on a ClinicalObservation (the column is
    `extraction_status`), which only surfaced once real rows flowed through
    build_signals. An empty cohort hid it, so this test imports a document first.
    """
    tid = uuid.uuid4()
    pid = _patient(client, tid)
    body = {"patient_id": pid, "document_type": "lab_report",
            "text": "HbA1c 58 mmol/mol 2024-05-20\nBP 138/86 mmHg 2024-05-20",
            "reference_date": str(datetime(2024, 6, 1))}
    assert client.post("/documents", json=body, headers=_headers(tid)).status_code == 201

    r = client.get("/analytics/cohort", headers=_headers(tid))
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["n_patients"] == 1
    # HbA1c present and reconciled (58 mmol/mol -> ~7.5%) so the aggregate is non-null
    assert summary["mean_latest_hba1c"] is not None
    assert 6.0 <= summary["mean_latest_hba1c"] <= 9.0
