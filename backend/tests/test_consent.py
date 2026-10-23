import uuid
from datetime import datetime

from tests.conftest import _headers


def _patient(client, tid, *, consent=True):
    pid = client.post("/patients", json={"condition": "diabetes"}, headers=_headers(tid)).json()["id"]
    if consent:
        assert client.post(f"/patients/{pid}/consent", json={"purpose": "record_processing"},
                           headers=_headers(tid)).status_code == 201
    return pid


def _doc(pid):
    return {"patient_id": pid, "document_type": "lab_report",
            "text": "HbA1c 58 mmol/mol 2024-05-20", "reference_date": str(datetime(2024, 6, 1))}


def test_import_without_consent_is_forbidden(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid, consent=False)
    r = client.post("/documents", json=_doc(pid), headers=_headers(tid))
    assert r.status_code == 403
    assert "consent" in r.json()["detail"].lower()


def test_grant_then_import_and_read_allowed(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid)  # consent granted
    assert client.post("/documents", json=_doc(pid), headers=_headers(tid)).status_code == 201
    assert any(e["code"] == "HBA1C" for e in client.get(f"/patients/{pid}/timeline",
                                                        headers=_headers(tid)).json())


def test_revoke_blocks_subsequent_import_and_read(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid)
    assert client.post("/documents", json=_doc(pid), headers=_headers(tid)).status_code == 201

    rev = client.post(f"/patients/{pid}/consent/revoke", json={"purpose": "record_processing"},
                      headers=_headers(tid))
    assert rev.status_code == 201

    # reads of the individual patient's data now require consent again
    assert client.get(f"/patients/{pid}/timeline", headers=_headers(tid)).status_code == 403
    assert client.get(f"/patients/{pid}/risk", headers=_headers(tid)).status_code == 403
    assert client.post("/documents", json=_doc(pid), headers=_headers(tid)).status_code == 403


def test_regrant_after_revoke_restores_access(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid)
    client.post(f"/patients/{pid}/consent/revoke", json={"purpose": "record_processing"},
                headers=_headers(tid))
    assert client.get(f"/patients/{pid}/timeline", headers=_headers(tid)).status_code == 403
    client.post(f"/patients/{pid}/consent", json={"purpose": "record_processing"},
                headers=_headers(tid))
    assert client.get(f"/patients/{pid}/timeline", headers=_headers(tid)).status_code == 200


def test_consent_status_reflects_state(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid, consent=False)
    assert client.get(f"/patients/{pid}/consent", headers=_headers(tid)).json() == [
        {"purpose": "record_processing", "active": False}]
    client.post(f"/patients/{pid}/consent", json={"purpose": "record_processing"},
                headers=_headers(tid))
    assert client.get(f"/patients/{pid}/consent", headers=_headers(tid)).json() == [
        {"purpose": "record_processing", "active": True}]


def test_unknown_purpose_rejected(client):
    tid = uuid.uuid4()
    pid = _patient(client, tid, consent=False)
    r = client.post(f"/patients/{pid}/consent", json={"purpose": "marketing"},
                    headers=_headers(tid))
    assert r.status_code == 400


def test_cross_tenant_read_is_404_not_403(client):
    """We never confirm a patient exists in another tenant, even with consent there."""
    ta, tb = uuid.uuid4(), uuid.uuid4()
    pid = _patient(client, ta)  # consented in tenant A
    r = client.get(f"/patients/{pid}/timeline", headers=_headers(tb))
    assert r.status_code == 404


def test_consent_is_tenant_scoped(client):
    ta = uuid.uuid4()
    pid = _patient(client, ta, consent=False)
    assert client.post("/documents", json=_doc(pid), headers=_headers(ta)).status_code == 403
