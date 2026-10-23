"""Value objects shared across the clinical pipeline.

A CandidateFact is the untrusted output of extraction. It ALWAYS carries a
provenance pointer (source document + page + exact quote). Nothing downstream
may drop provenance: a fact without a citation is not allowed to reach a
clinician.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Provenance:
    source_document_id: uuid.UUID | None
    page: int | None = None
    quote: str = ""

    def is_traceable(self) -> bool:
        return self.source_document_id is not None and bool(self.quote)


@dataclass
class CandidateFact:
    """A fact extracted from a document, not yet validated."""

    code: str | None                 # raw or normalized terminology code
    observed_at: datetime | None
    provenance: Provenance
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)

    ambiguous: bool = False          # date/unit/value uncertain -> route to human


@dataclass
class ValidatedObservation:
    """A candidate fact that passed type/date/unit/terminology checks."""

    code: str
    observed_at: datetime | None
    value_numeric: float | None
    value_text: str | None
    unit: str | None                 # normalized canonical unit
    provenance: Provenance
    status: str                      # validated | flagged
    reason: str | None = None
