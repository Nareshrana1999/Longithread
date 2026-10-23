"""End-to-end reconciliation pipeline for a single patient's documents.

ingest -> extract -> quarantine check -> validate -> detect conflicts.

The quarantine boundary is a security invariant: text that tries to act like
instructions never produces observations at all. Everything that survives is
still just a *candidate* until validation promotes it, and conflicts are surfaced
not resolved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .conflicts import Conflict, detect_conflicts
from .extractor import DeterministicExtractor, Extractor
from .terminology import looks_like_prompt_injection
from .types import ValidatedObservation
from .validation import validate


@dataclass
class PipelineResult:
    observations: list[ValidatedObservation] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    quarantined_documents: list[uuid.UUID] = field(default_factory=list)
    flagged: list[ValidatedObservation] = field(default_factory=list)

    @property
    def validated(self) -> list[ValidatedObservation]:
        return [o for o in self.observations if o.status == "validated"]


def run_pipeline(
    documents: list[tuple[uuid.UUID, str, datetime | None]],
    extractor: Extractor | None = None,
) -> PipelineResult:
    """documents: list of (source_document_id, page_text, reference_date)."""
    extractor = extractor or DeterministicExtractor()
    result = PipelineResult()

    for doc_id, text, reference in documents:
        if looks_like_prompt_injection(text):
            # Untrusted steering text never becomes a clinical fact.
            result.quarantined_documents.append(doc_id)
            continue

        candidates = extractor.extract(text, source_document_id=doc_id,
                                       page=None, reference=reference)
        for cand in candidates:
            result.observations.append(validate(cand))

    result.observations = _dedup(result.observations)

    conflicts = detect_conflicts([(i, o) for i, o in enumerate(result.observations)])
    result.conflicts = conflicts
    result.flagged = [o for o in result.observations if o.status == "flagged"]
    return result


def _dedup(observations):
    """Collapse byte-identical facts (same code, timestamp, value, unit).

    A duplicated document must not double-count the same measurement. Different
    values for the same code+timestamp are NOT deduped - they flow to conflict
    detection instead.
    """
    seen: set = set()
    out = []
    for o in observations:
        key = (o.code, o.observed_at, o.value_numeric, o.value_text, o.unit)
        if key in seen:
            continue
        seen.add(key)
        out.append(o)
    return out
