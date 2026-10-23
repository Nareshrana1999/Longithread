"""Extraction: turn authorized document text into CandidateFacts.

Two backends ship here:
  * DeterministicExtractor - regex based, no network, the MVP default so the
    pipeline is evaluable without any API key.
  * LLMExtractor - optional hosted-model adapter behind a narrow interface.

Rule of the system: an LLM may propose candidate facts, but it may NEVER invent
a clinical value that is not traceable to a source quote, and it NEVER decides
treatment. Validation (validation.py) is what promotes a candidate.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Protocol

from .terminology import normalize_code, normalize_text_code
from .types import CandidateFact, Provenance

_UNITS = r"(?:%|mmol/mol|mg/dL|mmol/L|mmHg|umol/L|µmol/L|mEq/L)"
_VALUE_UNIT = re.compile(rf"([0-9]+(?:\.[0-9]+)?)\s*({_UNITS})", re.I)
_BP = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_TEXT_DATE = re.compile(
    r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})",
    re.I,
)
_RELATIVE = re.compile(r"(\d+)\s+(day|week|month|year)s?\s+ago", re.I)
_AFTER_COLON = re.compile(r":\s*(.+?)\s*$")
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _parse_date(text: str, reference: datetime | None) -> tuple[datetime | None, bool]:
    """Return (date, ambiguous). ISO/textual dates are exact; relative ones are
    ambiguous because the anchor ("ago from when?") is unreliable."""
    m = _ISO_DATE.search(text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))), False
    m = _TEXT_DATE.search(text)
    if m:
        return datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))), False
    m = _RELATIVE.search(text)
    if m and reference:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta = {"day": timedelta(days=n), "week": timedelta(weeks=n),
                 "month": timedelta(days=30 * n), "year": timedelta(days=365 * n)}[unit]
        return reference - delta, True
    return None, True


class Extractor(Protocol):
    def extract(self, text: str, source_document_id: uuid.UUID | None,
                page: int | None, reference: datetime | None = None) -> list[CandidateFact]: ...


class DeterministicExtractor:
    def extract(self, text: str, source_document_id: uuid.UUID | None,
                page: int | None = None, reference: datetime | None = None) -> list[CandidateFact]:
        facts: list[CandidateFact] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            date, ambiguous = _parse_date(line, reference)
            prov = Provenance(source_document_id=source_document_id, page=page, quote=line.strip())

            bp = _BP.search(line)
            if bp and "bp" in line.lower():
                for code, val in (("SBP", bp.group(1)), ("DBP", bp.group(2))):
                    facts.append(CandidateFact(
                        code=code, value_numeric=float(val), unit="mmHg",
                        observed_at=date, provenance=prov, ambiguous=ambiguous))

            low = line.lower()
            vu = _VALUE_UNIT.search(line)
            if vu:
                for code in _codes_in(low):
                    facts.append(CandidateFact(
                        code=code,
                        value_numeric=float(vu.group(1)),
                        unit=vu.group(2),
                        observed_at=date,
                        provenance=prov,
                        ambiguous=ambiguous,
                    ))

            text_code = normalize_text_code(low)
            if text_code:
                m = _AFTER_COLON.search(line)
                value_text = m.group(1).strip() if m else line.split(":", 1)[-1].strip()
                if value_text:
                    facts.append(CandidateFact(
                        code=text_code, value_text=value_text, observed_at=date,
                        provenance=prov, ambiguous=ambiguous,
                    ))
        return facts


def _codes_in(line_lower: str) -> list[str]:
    found, seen = [], set()
    for alias, canonical in _ALL_ALIASES:
        if alias in line_lower and canonical not in seen:
            seen.add(canonical)
            found.append(canonical)
    return found


# Precompiled alias list, longest alias first so "ldl cholesterol" wins over "ldl".
from .terminology import _CODE_ALIASES  # noqa: E402
_ALL_ALIASES = sorted(_CODE_ALIASES.items(), key=lambda kv: -len(kv[0]))


class LLMExtractor:
    """Optional hosted-model adapter. Deliberately unimplemented in the MVP to
    keep the laptop buildable and offline-deterministic; wire to a provider and
    route every returned fact through validation before use."""

    def __init__(self, api_key: str | None):
        if not api_key:
            raise RuntimeError("LLMExtractor requires an API key; use DeterministicExtractor instead")

    def extract(self, text, source_document_id, page=None, reference=None):  # pragma: no cover
        raise NotImplementedError
