import uuid
from datetime import datetime

from app.clinical.extractor import DeterministicExtractor

DOC = uuid.uuid4()


def _extract(text):
    return DeterministicExtractor().extract(text, source_document_id=DOC,
                                            page=1, reference=datetime(2024, 6, 1))


def test_extracts_hba1c_with_unit_and_date():
    facts = _extract("HbA1c 58 mmol/mol 2024-05-20")
    assert any(f.code == "HBA1C" and f.value_numeric == 58 and f.unit == "mmol/mol"
               and f.observed_at == datetime(2024, 5, 20) for f in facts)


def test_every_fact_carries_provenance():
    facts = _extract("LDL cholesterol 130 mg/dL 2024-01-05")
    assert facts, "expected at least one fact"
    assert all(f.provenance.is_traceable() for f in facts)
    assert all(f.provenance.source_document_id == DOC for f in facts)


def test_relative_date_is_marked_ambiguous():
    facts = _extract("LDL cholesterol 130 mg/dL 3 months ago")
    assert facts and all(f.ambiguous for f in facts)


def test_blood_pressure_splits_into_sbp_dbp():
    facts = _extract("BP 128/82 mmHg 2024-05-20")
    codes = {f.code for f in facts}
    assert {"SBP", "DBP"} <= codes


def test_medication_list_extracted_as_text():
    facts = _extract("Medication list 2024-05-01: Metformin")
    assert any(f.code == "MED_LIST" and f.value_text == "Metformin" for f in facts)
