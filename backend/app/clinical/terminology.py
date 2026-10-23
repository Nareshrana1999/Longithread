"""Terminology mapping + unit normalization.

Deliberately narrow: enough canonical concepts and unit conversions to
demonstrate the reconciliation pipeline and its error analysis. Extend the
catalogs with a clinical advisor before any real use; a wrong unit conversion
is a patient-safety bug, so every conversion here is explicit and tested.
"""

from __future__ import annotations

import re

# aliases -> canonical code (LOINC-style identifiers used symbolically)
_CODE_ALIASES: dict[str, str] = {
    "hba1c": "HBA1C",
    "hb_a1c": "HBA1C",
    "glycated hemoglobin": "HBA1C",
    "haemoglobin a1c": "HBA1C",
    "ldl": "LDL_CHOL",
    "ldl cholesterol": "LDL_CHOL",
    "ldl-c": "LDL_CHOL",
    "hdl": "HDL_CHOL",
    "creatinine": "CREATININE",
    "serum creatinine": "CREATININE",
    "systolic": "SBP",
    "systolic bp": "SBP",
    "diastolic": "DBP",
    "diastolic bp": "DBP",
    "potassium": "POTASSIUM",
    "sodium": "SODIUM",
}

# canonical code -> set of allowed units, with the preferred canonical unit.
_UNIT_DOMAINS: dict[str, dict[str, str]] = {
    "HBA1C": {"%": "%", "mmol/mol": "mmol/mol"},
    "LDL_CHOL": {"mg/dL": "mg/dL", "mmol/L": "mmol/L"},
    "HDL_CHOL": {"mg/dL": "mg/dL", "mmol/L": "mmol/L"},
    "CREATININE": {"mg/dL": "mg/dL", "umol/L": "umol/L", "µmol/L": "umol/L"},
    "SBP": {"mmHg": "mmHg"},
    "DBP": {"mmHg": "mmHg"},
    "POTASSIUM": {"mmol/L": "mmol/L", "mEq/L": "mmol/L"},
    "SODIUM": {"mmol/L": "mmol/L", "mEq/L": "mmol/L"},
}

# Labels whose value is free text (no numeric/unit), used for contradictory-record
# detection such as conflicting medication lists.
TEXT_CODE_ALIASES: dict[str, str] = {
    "medication list": "MED_LIST",
    "med list": "MED_LIST",
    "current medications": "MED_LIST",
}


def normalize_text_code(raw: str) -> str | None:
    """Map a text label if one appears in the line (longest alias wins)."""
    low = raw.lower()
    for alias, canonical in sorted(TEXT_CODE_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in low:
            return canonical
    return None


def normalize_code(raw: str) -> str | None:
    key = raw.strip().lower()
    if key in _CODE_ALIASES:
        return _CODE_ALIASES[key]
    if raw in _CODE_ALIASES.values():      # already canonical (e.g. HBA1C, MED_LIST)
        return raw
    if raw in TEXT_CODE_ALIASES.values():
        return raw
    return None


def canonicalize_value(code: str, value: float, unit: str) -> tuple[float, str]:
    """Return (value, canonical_unit). Raises ValueError on unknown unit."""
    domain = _UNIT_DOMAINS.get(code)
    if domain is None:
        raise ValueError(f"no unit domain for code {code}")
    if unit not in domain:
        raise ValueError(f"unit {unit!r} not permitted for {code}")
    canon = domain[unit]
    if code == "HBA1C" and unit == "mmol/mol":
        # IFCC mmol/mol -> NGSP %
        return round(value / 10.929 + 2.15, 2), "%"
    if code in ("LDL_CHOL", "HDL_CHOL") and unit == "mmol/L":
        return round(value * 38.67, 1), "mg/dL"  # cholesterol molar mass factor
    if code == "CREATININE" and unit == "umol/L":
        return round(value / 88.4, 2), "mg/dL"
    return value, canon


def is_permitted_unit(code: str, unit: str) -> bool:
    domain = _UNIT_DOMAINS.get(code)
    return bool(domain) and unit in domain


# Label text we accept before a value, used by the deterministic extractor.
def label_for(code: str) -> str:
    for alias, canonical in _CODE_ALIASES.items():
        if canonical == code:
            return alias
    return code.lower()


_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|system)\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(rules|instructions|protocol)", re.I),
    re.compile(r"mark\s+all\s+tasks\s+(as\s+)?complete", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"system\s*:", re.I),
]


def looks_like_prompt_injection(text: str) -> bool:
    """Detect document text that tries to steer the AI, so it can be quarantined.

    This is a heuristic safety net for the MVP; a real deployment needs a proper
    untrusted-content boundary where document text is NEVER treated as instructions.
    """
    return any(p.search(text) for p in _INJECTION_PATTERNS)
