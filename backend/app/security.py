"""Request-scoped tenant context and audit logging.

Tenant isolation is enforced here at the data-access layer (every query is
filtered by tenant) and must ALSO be enforced with database RLS policies in
production. Never rely on the UI alone.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import record_audit
from .db import get_session
from .models import AuditEvent


@dataclass(frozen=True)
class TenantContext:
    tenant_id: uuid.UUID
    actor_id: uuid.UUID | None
    role: str


def get_current_context(
    x_tenant_id: str = Header(..., description="Tenant scope for this request"),
    x_user_id: str | None = Header(default=None),
    x_user_role: str = Header(default="coordinator"),
) -> TenantContext:
    """Minimal header-based identity for the MVP.

    Replace with real authentication (JWT / session tokens) before any pilot.
    The tenant id is validated to be a well-formed UUID and is the only source
    of truth for row scoping.
    """
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid tenant id") from exc

    actor_id = None
    if x_user_id:
        try:
            actor_id = uuid.UUID(x_user_id)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid user id") from exc

    return TenantContext(tenant_id=tenant_id, actor_id=actor_id, role=x_user_role)


def scoped(session: Session, model, ctx: TenantContext):
    """Return a SELECT already filtered to the caller's tenant."""
    return select(model).where(model.tenant_id == ctx.tenant_id)


def log_action(
    session: Session,
    ctx: TenantContext,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    detail: dict | None = None,
) -> AuditEvent:
    return record_audit(session, ctx.tenant_id, ctx.actor_id, action, entity_type, entity_id, detail)


DbSession = Depends(get_session)
Ctx = Depends(get_current_context)
