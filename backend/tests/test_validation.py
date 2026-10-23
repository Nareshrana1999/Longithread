from datetime import datetime

from app.clinical.extractor import DeterministicExtractor
from app.clinical.validation import validate
import uuid

DOC = uuid.uuid4()


def _one(text):
    facts = DeterministicExtractor().extract(text, source_document_id=DOC, reference=datetime(2024, 6, 1))
    return validate(facts[0])


def test_mmol_per_mol_canonicalizes_to_percent():
    obs = _one("HbA1c 58 mmol/mol 2024-05-20")
    assert obs.status == "validated"
    assert obs.unit == "%"
    assert abs(obs.value_numeric - 7.46) < 0.05


def test_out_of_range_value_is_flagged():
    obs = _one("HbA1c 500 % 2024-05-20")
    assert obs.status == "flagged"
    assert "plausible range" in (obs.reason or "")


def test_permitted_regex_unit_wrong_domain_is_flagged():
    obs = _one("HbA1c 58 mg/dL 2024-05-20")
    assert obs.status == "flagged"
    assert "not permitted" in (obs.reason or "")


def test_missing_date_is_flagged_not_silent():
    facts = DeterministicExtractor().extract("LDL cholesterol 130 mg/dL", source_document_id=DOC)
    obs = validate(facts[0])
    assert obs.status == "flagged"
