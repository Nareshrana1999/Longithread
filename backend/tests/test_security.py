import uuid
from datetime import datetime

import pytest

from app import service
from app.models import Patient
from app.security import TenantContext

REF = datetime(2024, 6, 1)


def _ctx(tenant):
    return TenantContext(tenant_id=tenant, actor_id=uuid.uuid4(), role="clinician")


def test_cannot_import_into_another_tenants_patient(db):
    ta, tb = uuid.uuid4(), uuid.uuid4()
    patient = Patient(tenant_id=ta, condition="diabetes")
    db.add(patient)
    db.commit()

    with pytest.raises(PermissionError):
        service.import_document(db, _ctx(tb), patient_id=patient.id,
                                document_type="lab_report",
                                text="HbA1c 58 mmol/mol 2024-05-20", reference_date=REF)
    db.rollback()


def test_queries_are_tenant_scoped(db):
    ta, tb = uuid.uuid4(), uuid.uuid4()
    pa = Patient(tenant_id=ta)
    pb = Patient(tenant_id=tb)
    db.add_all([pa, pb])
    db.commit()

    service.import_document(db, _ctx(ta), patient_id=pa.id, document_type="lab_report",
                            text="HbA1c 58 mmol/mol 2024-05-20", reference_date=REF)
    db.commit()

    # tenant B sees nothing of tenant A's data
    assert service.patient_observations(db, _ctx(tb), pa.id) == []
    # tenant B querying by A's patient id returns no rows
    assert service.patient_observations(db, _ctx(tb), pb.id) == []
    # tenant A sees its own
    assert len(service.patient_observations(db, _ctx(ta), pa.id)) >= 1
