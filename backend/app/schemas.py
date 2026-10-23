"""Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class PatientCreate(BaseModel):
    external_ref: str | None = None
    condition: str | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    external_ref: str | None
    condition: str | None


class DocumentIn(BaseModel):
    patient_id: uuid.UUID
    document_type: str
    # Plain text for the MVP; production replaces this with encrypted object storage
    # and an ingestion job for PDFs / scanned images.
    text: str
    reference_date: datetime | None = None

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document text must not be blank")
        return v


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    observed_at: datetime | None
    extraction_status: str
    source_document_id: uuid.UUID | None


class TimelineEntry(BaseModel):
    observed_at: datetime | None
    code: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    status: str
    reason: str | None = None
    source_document_id: uuid.UUID | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rule_id: str
    rule_version: str
    status: str
    due_at: datetime | None


class ImportResult(BaseModel):
    document_id: uuid.UUID
    quarantined: bool
    observations_created: int
    flagged: int
    conflicts: int
