"""FastAPI application - Longithread MVP.

Run:  uvicorn app.main:app --reload
Every route is scoped to the caller's tenant and writes an audit event on state
change. Risk and analytics outputs are decision support for clinicians, never
autonomous diagnosis or treatment. This is a developer MVP, not a medical device.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import service
from .analytics.cohort import summarize_cohort
from .audit import list_events, verify_audit_chain
from .consent import (RECORD_PROCESSING, ConsentNotOnFile, UnknownPurpose,
                      VALID_PURPOSES)
from .db import SessionLocal, get_session, init_db
from .jobs.queue import default_runner
from .ml.risk import default_model
from .models import FollowUpTask, Patient
from .rules.engine import PROTOCOLS
from .schemas import (AuditEventOut, ConsentIn, ConsentOut, ConsentStatus,
                      DocumentIn, ImportResult, ObservationOut, PatientCreate,
                      PatientOut, TaskOut, TimelineEntry)
from .security import TenantContext, get_current_context, log_action, scoped

DASHBOARD = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


def _guard_patient(session: Session, ctx: TenantContext, patient_id: uuid.UUID) -> None:
    """404 if the patient is not in this tenant; 403 if no lawful basis to process.

    Order matters: a cross-tenant probe returns 404 (we never confirm existence),
    and only an in-tenant patient without active consent returns 403.
    """
    if service.get_patient(session, ctx, patient_id) is None:
        raise HTTPException(404, "patient not found in this tenant")
    try:
        service.require_active_consent(session, ctx, patient_id, RECORD_PROCESSING)
    except ConsentNotOnFile as exc:
        raise HTTPException(403, "no active consent on file to process this patient") from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    # The in-process job runner uses daemon-like pool threads; leaving it running
    # avoids poisoning the shared runner across multiple app lifespans in tests.


app = FastAPI(title="Longithread", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "Longithread", "note": "developer MVP - not a medical device"}


@app.get("/", include_in_schema=False)
def home():
    if DASHBOARD.exists():
        return FileResponse(DASHBOARD, media_type="text/html")
    return JSONResponse({"product": "Longithread", "docs": "/docs", "note": "frontend/dashboard not built"})


@app.post("/patients", response_model=PatientOut, status_code=201)
def create_patient(payload: PatientCreate, session: Session = Depends(get_session),
                   ctx: TenantContext = Depends(get_current_context)) -> Patient:
    patient = Patient(tenant_id=ctx.tenant_id, external_ref=payload.external_ref,
                      condition=payload.condition)
    session.add(patient)
    session.flush()
    log_action(session, ctx, "patient.created", "patient", patient.id, {})
    session.commit()
    return patient


@app.get("/patients", response_model=list[PatientOut])
def list_patients(session: Session = Depends(get_session),
                  ctx: TenantContext = Depends(get_current_context)):
    return service.list_patients(session, ctx)


@app.post("/documents", response_model=ImportResult, status_code=201)
def import_document(payload: DocumentIn, session: Session = Depends(get_session),
                    ctx: TenantContext = Depends(get_current_context)) -> ImportResult:
    _guard_patient(session, ctx, payload.patient_id)
    try:
        out = service.import_document(
            session, ctx, patient_id=payload.patient_id, document_type=payload.document_type,
            text=payload.text, reference_date=payload.reference_date)
    except PermissionError:
        raise HTTPException(404, "patient not found in this tenant")
    session.commit()
    return ImportResult(
        document_id=out["document_id"], quarantined=out["quarantined"],
        observations_created=out["observations_created"], flagged=out["flagged"],
        conflicts=out["conflicts"])


@app.get("/patients/{patient_id}/observations", response_model=list[ObservationOut])
def list_observations(patient_id: uuid.UUID, session: Session = Depends(get_session),
                      ctx: TenantContext = Depends(get_current_context)):
    _guard_patient(session, ctx, patient_id)
    return service.patient_observations(session, ctx, patient_id)


@app.get("/patients/{patient_id}/timeline", response_model=list[TimelineEntry])
def timeline(patient_id: uuid.UUID, session: Session = Depends(get_session),
             ctx: TenantContext = Depends(get_current_context)):
    _guard_patient(session, ctx, patient_id)
    obs = service.patient_observations(session, ctx, patient_id)
    entries = [
        TimelineEntry(observed_at=o.observed_at, code=o.code, value_numeric=o.value_numeric,
                      value_text=o.value_text, unit=o.unit, status=o.extraction_status,
                      reason=None, source_document_id=o.source_document_id)
        for o in obs
    ]
    entries.sort(key=lambda e: (e.observed_at is None, e.observed_at or datetime.min))
    return entries


@app.post("/patients/{patient_id}/tasks/generate", response_model=list[TaskOut])
def generate_tasks(patient_id: uuid.UUID, protocol: str = "diabetes_v1",
                   session: Session = Depends(get_session),
                   ctx: TenantContext = Depends(get_current_context)):
    if protocol not in PROTOCOLS:
        raise HTTPException(400, f"unknown protocol; one of {sorted(PROTOCOLS)}")
    _guard_patient(session, ctx, patient_id)
    tasks = service.generate_tasks(session, ctx, patient_id, protocol=protocol)
    session.commit()
    return tasks


@app.get("/patients/{patient_id}/tasks", response_model=list[TaskOut])
def list_tasks(patient_id: uuid.UUID, session: Session = Depends(get_session),
               ctx: TenantContext = Depends(get_current_context)):
    return list(session.scalars(scoped(session, FollowUpTask, ctx).where(
        FollowUpTask.patient_id == patient_id)))


@app.post("/tasks/{task_id}/review", response_model=TaskOut)
def review_task(task_id: uuid.UUID, decision: str = Header(alias="X-Decision"),
                session: Session = Depends(get_session),
                ctx: TenantContext = Depends(get_current_context)):
    """Human-in-the-loop: a clinician/coordinator records what they decided."""
    if decision not in {"accepted", "rejected", "done"}:
        raise HTTPException(400, "decision must be accepted|rejected|done")
    task = session.scalars(scoped(session, FollowUpTask, ctx).where(FollowUpTask.id == task_id)).first()
    if task is None:
        raise HTTPException(404, "task not found in this tenant")
    task.status = decision
    task.reviewed_by = ctx.actor_id
    log_action(session, ctx, f"task.{decision}", "follow_up_task", task.id, {})
    session.commit()
    return task


# ---------------- AI decision support + analytics ----------------

@app.get("/ml/model")
def ml_model(ctx: TenantContext = Depends(get_current_context)):
    model, metrics = default_model()
    return {
        "model": "logistic_regression_v1",
        "purpose": "clinician-facing deterioration-risk decision support (synthetic baseline)",
        "features": model.features,
        "weights": dict(zip(model.features, [round(w, 4) for w in model.weights])),
        "metrics_on_synthetic_holdout": metrics,
        "not_for": "autonomous diagnosis, treatment changes, or real-world claims",
    }


@app.get("/patients/{patient_id}/risk")
def patient_risk(patient_id: uuid.UUID, as_of: datetime | None = None,
                 session: Session = Depends(get_session),
                 ctx: TenantContext = Depends(get_current_context)):
    _guard_patient(session, ctx, patient_id)
    assessment = service.risk_for_patient(session, ctx, patient_id, as_of=as_of)
    return asdict(assessment)


@app.get("/analytics/cohort")
def cohort_analytics(as_of: datetime | None = None, session: Session = Depends(get_session),
                     ctx: TenantContext = Depends(get_current_context)):
    records = service.cohort_records(session, ctx)
    return summarize_cohort(records, as_of=as_of).to_dict()


# ---------------- consent / lawful basis ----------------

@app.post("/patients/{patient_id}/consent", response_model=ConsentOut, status_code=201)
def grant_consent(patient_id: uuid.UUID, payload: ConsentIn,
                  session: Session = Depends(get_session),
                  ctx: TenantContext = Depends(get_current_context)):
    if payload.purpose not in VALID_PURPOSES:
        raise HTTPException(400, f"unknown purpose; one of {sorted(VALID_PURPOSES)}")
    try:
        record = service.grant_consent(session, ctx, patient_id,
                                       purpose=payload.purpose, basis=payload.basis)
    except PermissionError:
        raise HTTPException(404, "patient not found in this tenant")
    except UnknownPurpose as exc:
        raise HTTPException(400, f"unknown purpose: {exc}") from exc
    session.commit()
    return record


@app.post("/patients/{patient_id}/consent/revoke", response_model=ConsentOut, status_code=201)
def revoke_consent(patient_id: uuid.UUID, payload: ConsentIn,
                   session: Session = Depends(get_session),
                   ctx: TenantContext = Depends(get_current_context)):
    if payload.purpose not in VALID_PURPOSES:
        raise HTTPException(400, f"unknown purpose; one of {sorted(VALID_PURPOSES)}")
    try:
        record = service.revoke_consent(session, ctx, patient_id, purpose=payload.purpose)
    except PermissionError:
        raise HTTPException(404, "patient not found in this tenant")
    session.commit()
    return record


@app.get("/patients/{patient_id}/consent", response_model=list[ConsentStatus])
def consent_status(patient_id: uuid.UUID, session: Session = Depends(get_session),
                   ctx: TenantContext = Depends(get_current_context)):
    if service.get_patient(session, ctx, patient_id) is None:
        raise HTTPException(404, "patient not found in this tenant")
    return [ConsentStatus(purpose=p, active=service.has_active_consent(session, ctx, patient_id, p))
            for p in sorted(VALID_PURPOSES)]


# ---------------- tamper-evident audit ----------------

@app.get("/audit/verify")
def audit_verify(session: Session = Depends(get_session),
                 ctx: TenantContext = Depends(get_current_context)):
    """Integrity check of the caller's tenant audit chain. `valid: false` means the
    append-only history was edited, deleted, or reordered somewhere."""
    return verify_audit_chain(session, ctx.tenant_id)


@app.get("/audit/events", response_model=list[AuditEventOut])
def audit_events(entity_type: str | None = None, entity_id: uuid.UUID | None = None,
                 session: Session = Depends(get_session),
                 ctx: TenantContext = Depends(get_current_context)):
    return list_events(session, ctx.tenant_id, entity_type=entity_type, entity_id=entity_id)


# ---------------- async import jobs ----------------

@app.post("/jobs/import", status_code=202)
def enqueue_import(payload: DocumentIn, session: Session = Depends(get_session),
                   ctx: TenantContext = Depends(get_current_context)):
    # Check existence + lawful basis synchronously before accepting the job.
    _guard_patient(session, ctx, payload.patient_id)

    def _work():
        db = SessionLocal()
        try:
            out = service.import_document(
                db, ctx, patient_id=payload.patient_id, document_type=payload.document_type,
                text=payload.text, reference_date=payload.reference_date)
            db.commit()
            return out
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    job_id = default_runner.submit("document.import", _work)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str, ctx: TenantContext = Depends(get_current_context)):
    job = default_runner.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return {"job_id": job.id, "kind": job.kind, "status": job.status,
            "result": job.result, "error": job.error, "finished_at": job.finished_at}
