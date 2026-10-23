"""Audit trail writes. Append-only by convention and (in prod) by DB grants."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from .models import AuditEvent


def record_audit(
    session: Session,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
    )
    session.add(event)
    session.flush()
    return event
