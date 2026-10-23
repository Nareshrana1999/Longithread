"""Persistence orchestration: turns pipeline output into tenant-scoped rows.

De-duplicates identical documents by content_hash, quarantines injection text,
writes observations with provenance, runs the approved rules, and records every
action in the audit trail.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .clinical.pipeline import run_pipeline
from .models import ClinicalObservation, FollowUpTask, Patient, SourceDocument
from .rules.engine import PROTOCOLS, evaluate
from .security import TenantContext, log_action, scoped


def _now() -> datetime:
    # Naive UTC, consistent with observed_at values parsed from documents and
    # returned by the DB driver (which yields naive datetimes).
    return datetime.now(timezone.utc).replace(tzinfo=None)


def import_document(session: Session, ctx: TenantContext, *, patient_id: uuid.UUID,
                    document_type: str, text: str, reference_date: datetime | None) -> dict:
    # Verify the patient belongs to this tenant BEFORE touching any data.
    patient = session.scalars(scoped(session, Patient, ctx).where(Patient.id == patient_id)).first()
    if patient is None:
        raise PermissionError("patient not found in this tenant")

    content_hash = hashlib.sha256(text.encode()).hexdigest()

    # Idempotency: same content already imported -> no duplicate observations.
    existing = session.scalars(
        select(SourceDocument).where(
            SourceDocument.tenant_id == ctx.tenant_id,
            SourceDocument.patient_id == patient_id,
            SourceDocument.content_hash == content_hash,
        )
    ).first()
    if existing is not None:
        return {"document_id": existing.id, "quarantined": existing.is_quarantined,
                "observations_created": 0, "flagged": 0, "conflicts": 0, "deduplicated": True}

    from .clinical.terminology import looks_like_prompt_injection
    quarantined = looks_like_prompt_injection(text)
    doc = SourceDocument(
        tenant_id=ctx.tenant_id, patient_id=patient_id, document_type=document_type,
        storage_key=f"mem:{content_hash}", content_hash=content_hash, is_quarantined=quarantined,
    )
    session.add(doc)
    session.flush()

    if quarantined:
        log_action(session, ctx, "document.quarantined", "source_document", doc.id,
                   {"reason": "prompt-injection heuristic"})
        return {"document_id": doc.id, "quarantined": True, "observations_created": 0,
                "flagged": 0, "conflicts": 0, "deduplicated": False}

    result = run_pipeline([(doc.id, text, reference_date)])
    created = 0
    for obs in result.observations:
        session.add(ClinicalObservation(
            tenant_id=ctx.tenant_id, patient_id=patient_id, source_document_id=obs.provenance.source_document_id,
            code=obs.code, value_numeric=obs.value_numeric, value_text=obs.value_text,
            unit=obs.unit, observed_at=obs.observed_at, extraction_status=obs.status,
        ))
        created += 1

    log_action(session, ctx, "document.imported", "source_document", doc.id,
               {"observations": created, "conflicts": len(result.conflicts)})
    return {"document_id": doc.id, "quarantined": False, "observations_created": created,
            "flagged": len(result.flagged), "conflicts": len(result.conflicts), "deduplicated": False}


def patient_observations(session: Session, ctx: TenantContext, patient_id: uuid.UUID) -> list[ClinicalObservation]:
    return list(session.scalars(
        scoped(session, ClinicalObservation, ctx).where(ClinicalObservation.patient_id == patient_id)
    ))


def generate_tasks(session: Session, ctx: TenantContext, patient_id: uuid.UUID,
                    protocol: str = "diabetes_v1", as_of: datetime | None = None) -> list[FollowUpTask]:
    rules = PROTOCOLS[protocol]
    as_of = as_of or _now()
    obs = patient_observations(session, ctx, patient_id)
    suggestions = evaluate(rules, obs, as_of)

    tasks: list[FollowUpTask] = []
    for sug in suggestions:
        if sug.state != "due":
            # not_due and RECORD_MISSING create no automated task; RECORD_MISSING
            # is surfaced to a human in the timeline/review queue instead.
            continue
        # Avoid duplicate pending tasks for the same rule + due date.
        dup = session.scalars(
            scoped(session, FollowUpTask, ctx).where(
                FollowUpTask.patient_id == patient_id,
                FollowUpTask.rule_id == sug.rule_id,
                FollowUpTask.status == "pending",
            )
        ).first()
        if dup:
            tasks.append(dup)
            continue
        task = FollowUpTask(
            tenant_id=ctx.tenant_id, patient_id=patient_id, rule_id=sug.rule_id,
            rule_version=sug.rule_version, status="pending", due_at=sug.due_at,
        )
        session.add(task)
        session.flush()
        log_action(session, ctx, "task.created", "follow_up_task", task.id,
                   {"rule": sug.rule_id, "rationale": sug.rationale})
        tasks.append(task)
    return tasks


def list_patients(session: Session, ctx: TenantContext) -> list[Patient]:
    return list(session.scalars(scoped(session, Patient, ctx)))


def cohort_records(session: Session, ctx: TenantContext) -> list[dict]:
    """Bundle each tenant patient with their observations + tasks for analysis."""
    patients = list(session.scalars(scoped(session, Patient, ctx)))
    # Cohort aggregates are derived only from validated observations, matching the
    # risk path. Flagged (conflicting/unreviewed) records must not move a metric.
    obs_all = [o for o in session.scalars(scoped(session, ClinicalObservation, ctx))
               if o.extraction_status == "validated"]
    tasks_all = list(session.scalars(scoped(session, FollowUpTask, ctx)))
    by_p_obs: dict = {}
    by_p_task: dict = {}
    for o in obs_all:
        by_p_obs.setdefault(o.patient_id, []).append(o)
    for t in tasks_all:
        by_p_task.setdefault(t.patient_id, []).append(t)
    return [
        {"patient_id": str(p.id), "condition": p.condition,
         "observations": by_p_obs.get(p.id, []), "tasks": by_p_task.get(p.id, [])}
        for p in patients
    ]


def risk_for_patient(session: Session, ctx: TenantContext, patient_id: uuid.UUID,
                     as_of: datetime | None = None):
    from .ml.risk import score_patient

    patient = session.scalars(scoped(session, Patient, ctx).where(Patient.id == patient_id)).first()
    if patient is None:
        raise PermissionError("patient not found in this tenant")
    validated = [o for o in patient_observations(session, ctx, patient_id)
                 if o.extraction_status == "validated"]
    return score_patient(validated, as_of=as_of)

