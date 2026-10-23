import uuid

from sqlalchemy import select

from app.audit import GENESIS
from app.models import AuditEvent
from tests.conftest import _headers


def _generate_events(client, tid):
    """Create a tenant with three audit events: patient.created, consent.granted,
    document.imported -> seq 1,2,3 chained."""
    pid = client.post("/patients", json={"condition": "diabetes"},
                      headers=_headers(tid)).json()["id"]
    client.post(f"/patients/{pid}/consent", json={"purpose": "record_processing"},
                headers=_headers(tid))
    client.post("/documents", json={"patient_id": pid, "document_type": "lab_report",
                "text": "HbA1c 60 mmol/mol 2024-01-10", "reference_date": "2024-06-01T00:00:00"},
                headers=_headers(tid))
    return pid


def _rows(db, tid):
    return list(db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tid)
                           .order_by(AuditEvent.seq.asc())))


def test_chain_links_and_starts_at_genesis(client, db):
    tid = uuid.uuid4()
    _generate_events(client, tid)
    rows = _rows(db, tid)
    assert [r.seq for r in rows] == [1, 2, 3]
    assert rows[0].prev_hash == GENESIS
    for prev, nxt in zip(rows, rows[1:]):
        assert nxt.prev_hash == prev.content_hash


def test_verify_reports_valid_for_untouched_chain(client, db):
    tid = uuid.uuid4()
    _generate_events(client, tid)
    v = client.get("/audit/verify", headers=_headers(tid)).json()
    assert v["valid"] is True
    assert v["checked"] == 3
    assert v["first_bad_seq"] is None


def test_editing_a_record_breaks_the_chain(client, db):
    tid = uuid.uuid4()
    _generate_events(client, tid)
    target = next(r for r in _rows(db, tid) if r.seq == 2)
    target.detail = {"tampered": True}  # simulate a DB-level edit
    db.commit()

    v = client.get("/audit/verify", headers=_headers(tid)).json()
    assert v["valid"] is False
    assert v["first_bad_seq"] == 2
    assert "content_mismatch" in v["reasons"]


def test_deleting_a_middle_record_breaks_the_chain(client, db):
    tid = uuid.uuid4()
    _generate_events(client, tid)
    db.query(AuditEvent).filter(AuditEvent.tenant_id == tid, AuditEvent.seq == 2).delete()
    db.commit()

    v = client.get("/audit/verify", headers=_headers(tid)).json()
    assert v["valid"] is False
    assert v["first_bad_seq"] == 3
    assert "sequence_gap" in v["reasons"] or "broken_link" in v["reasons"]


def test_audit_events_endpoint_is_tenant_scoped(client, db):
    ta, tb = uuid.uuid4(), uuid.uuid4()
    _generate_events(client, ta)
    events_b = client.get("/audit/events", headers=_headers(tb)).json()
    assert events_b == []  # tenant B sees none of tenant A's history
    events_a = client.get("/audit/events", headers=_headers(ta)).json()
    assert [e["seq"] for e in events_a] == [1, 2, 3]
