from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    external_ref: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    documents: Mapped[list[SourceDocument]] = relationship(back_populates="patient")
    observations: Mapped[list[ClinicalObservation]] = relationship(back_populates="patient")
    tasks: Mapped[list[FollowUpTask]] = relationship(back_populates="patient")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped[Patient] = relationship(back_populates="documents")
    observations: Mapped[list[ClinicalObservation]] = relationship(back_populates="source_document")


class ClinicalObservation(Base):
    __tablename__ = "clinical_observations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"), nullable=False, index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("source_documents.id"))
    code: Mapped[str] = mapped_column(Text, nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime)
    extraction_status: Mapped[str] = mapped_column(String, nullable=False, default="extracted")
    conflict_with: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped[Patient] = relationship(back_populates="observations")
    source_document: Mapped[SourceDocument | None] = relationship(back_populates="observations")


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped[Patient] = relationship(back_populates="tasks")


class AuditEvent(Base):
    """Append-only, hash-chained per tenant. Never update or delete rows.

    ``content_hash`` commits to every field of this event plus ``prev_hash`` (the
    ``content_hash`` of the previous event in the same tenant chain). Editing,
    deleting, or reordering any earlier event therefore breaks the chain at that
    point, so ``verify_audit_chain`` can detect tampering rather than merely
    recording history.
    """

    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)


class ConsentRecord(Base):
    """A patient's lawful basis for processing, per purpose. Append-only history.

    The latest row for a (tenant, patient, purpose) sets the state: granted=True
    is active, granted=False is revoked. Importing or reading an individual
    patient's clinical data requires active consent for the relevant purpose.
    """

    __tablename__ = "consent_records"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    basis: Mapped[str] = mapped_column(String, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
