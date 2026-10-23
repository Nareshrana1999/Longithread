"""Conflict detection: surface contradictory records, never silently pick one.

Two observations "conflict" when they share a code and a timestamp but differ
materially in value. The blueprint's core safety property: contradictions are
highlighted for a human, not resolved by an automated tie-break.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .types import ValidatedObservation

# relative tolerance before two same-timestamp values are considered a conflict
_TOLERANCE = 0.10


@dataclass
class Conflict:
    a_id: object
    b_id: object
    code: str
    reason: str


def detect_conflicts(observations: list[tuple[object, ValidatedObservation]]) -> list[Conflict]:
    """Input is a list of (id, observation). Returns conflicts and mutates each
    involved observation's status to 'flagged'."""
    buckets: dict[tuple[str, object], list[tuple[object, ValidatedObservation]]] = defaultdict(list)
    for oid, obs in observations:
        if obs.status == "flagged":
            continue
        key = (obs.code, obs.observed_at)
        buckets[key].append((oid, obs))

    conflicts: list[Conflict] = []
    for (code, _when), group in buckets.items():
        if len(group) < 2:
            continue
        numeric = [(oid, o) for oid, o in group if o.value_numeric is not None]
        if not numeric:
            # text values (e.g. medication lists) conflict when they differ
            distinct_text = {o.value_text for _, o in group if o.value_text}
            if len(distinct_text) > 1:
                _mark_group(group)
                conflicts.append(Conflict(group[0][0], group[1][0], code,
                                          "contradictory text values at same timestamp"))
            continue
        vals = [o.value_numeric for _, o in numeric]
        lo, hi = min(vals), max(vals)
        if lo and (hi - lo) / max(lo, 1e-9) > _TOLERANCE:
            _mark_group(group)
            conflicts.append(Conflict(numeric[0][0], numeric[1][0], code,
                                      f"value spread {lo}..{hi} exceeds tolerance"))
    return conflicts


def _mark_group(group):
    for _oid, obs in group:
        obs.status = "flagged"
        obs.reason = (obs.reason or "") + " | conflicts with same-timestamp record"
