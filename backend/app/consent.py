"""Consent / lawful-basis model for processing a patient's clinical records.

A single, explicit purpose governs record processing so that the check is
unambiguous. In production this expands to per-purpose, per-scope authorizations
and is enforced with database-level policies, not only in the API layer.
"""

from __future__ import annotations

RECORD_PROCESSING = "record_processing"
VALID_PURPOSES = {RECORD_PROCESSING}


class ConsentNotOnFile(Exception):
    """Raised when processing is requested without an active lawful basis."""


class UnknownPurpose(Exception):
    """Raised when a request names a purpose the system does not recognize."""
