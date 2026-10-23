"""Tamper-evident audit trail.

Every event is appended to a per-tenant hash chain: ``content_hash`` commits to
the event's own fields plus the previous event's ``content_hash``. Editing,
deleting, or reordering any earlier event breaks the chain from that point on, so
``verify_audit_chain`` distinguishes an intact history from a tampered one.

Production note: the append-only property must be enforced by the database
(no UPDATE/DELETE grants, or an immutable/RLS store). This chain makes tampering
detectable; it does not by itself make tampering impossible.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent

GENESIS = "0" * 64


def _utcnow() -> datetime:
    # Second precision keeps the hash stable across DB round-trips.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _canonical(event) -> str:
    """Deterministic serialization of the fields committed to by ``content_hash``."""
    payload = {
        "seq": event.seq,
        "tenant_id": str(event.tenant_id),
        "actor_id": str(event.actor_id) if event.actor_id is not None else None,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": str(event.entity_id),
        "detail": event.detail or {},
        "created_at": event.created_at.isoformat(),
        "prev_hash": event.prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash(event) -> str:
    return hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()


def _last_event(session: Session, tenant_id: uuid.UUID) -> AuditEvent | None:
    return session.scalars(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.seq.desc())
        .limit(1)
    ).first()


def record_audit(
    session: Session,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    detail: dict | None = None,
) -> AuditEvent:
    prev = _last_event(session, tenant_id)
    event = AuditEvent(
        tenant_id=tenant_id,
        seq=(prev.seq + 1) if prev else 1,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
        created_at=_utcnow(),
        prev_hash=prev.content_hash if prev else GENESIS,
    )
    event.content_hash = _hash(event)
    session.add(event)
    session.flush()
    return event


def verify_audit_chain(session: Session, tenant_id: uuid.UUID) -> dict:
    """Recompute the chain and report the first integrity break, if any."""
    events = list(session.scalars(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.seq.asc())
    ))
    expected_prev = GENESIS
    expected_seq = 1
    for e in events:
        reasons = []
        if e.seq != expected_seq:
            reasons.append("sequence_gap")
        if e.prev_hash != expected_prev:
            reasons.append("broken_link")
        if e.content_hash != _hash(e):
            reasons.append("content_mismatch")
        if reasons:
            return {
                "tenant_id": str(tenant_id),
                "valid": False,
                "checked": len(events),
                "first_bad_seq": e.seq,
                "reasons": reasons,
            }
        expected_prev = e.content_hash
        expected_seq += 1
    return {
        "tenant_id": str(tenant_id),
        "valid": True,
        "checked": len(events),
        "first_bad_seq": None,
        "reasons": [],
    }


def list_events(session: Session, tenant_id: uuid.UUID, *,
                entity_type: str | None = None, entity_id: uuid.UUID | None = None,
                limit: int = 200) -> list[AuditEvent]:
    q = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if entity_type:
        q = q.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditEvent.entity_id == entity_id)
    q = q.order_by(AuditEvent.seq.asc()).limit(limit)
    return list(session.scalars(q))
