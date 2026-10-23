# Longithread

**Longitudinal care-coordination intelligence.** An evidence-backed layer that helps
clinical teams see what has happened to a patient, what follow-up is due, and which
records conflict — so nothing is lost between visits.

Built from a medical-AI startup blueprint. This is a **developer MVP** on synthetic
data — **clinical decision support, not a medical device, and not for patient care.**

---

## What it does

| Area | Capability |
| --- | --- |
| Ingestion | Authorized document text (PDF/OCR behind a seam) becomes structured facts |
| Extraction | Deterministic, offline extractor proposes candidate facts (optional LLM adapter behind the same seam) |
| Validation | Every fact is checked for traceable provenance, terminology, permitted unit, plausible range, unambiguous date — or **flagged** |
| Reconciliation | Same measurement across unit systems collapses; duplicates removed; contradictions are **surfaced, never auto-resolved** |
| Follow-up rules | Versioned, clinician-approved protocols create tasks; distinguishes `RECORD_MISSING` from "never performed" |
| AI decision support | Transparent logistic-regression deterioration risk with factor attribution, provenance, and **abstention** when data is thin |
| Cohort analytics | Follow-up completion, overdue load, monitoring-gap rate, HbA1c trends — from validated data only |
| Safety & governance | Prompt-injection quarantine, tenant isolation, append-only audit trail |

## What it does *not* do (and won't claim)

No medical-AI product can proveably have "no errors." Longithread is honest about the
rest: it **never invents clinical values**, **never diagnoses autonomously**, and
**never changes treatment**. Every output is a suggestion under clinician oversight,
traceable to its source, with accuracy measured against thresholds set before results.
The risk model is a **synthetic baseline** — a plumbing demo, not clinical evidence.

## Quickstart

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git-Bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload            # dashboard at http://127.0.0.1:8000/
```

```bash
python -m pytest                         # 39 tests
python -m tests.eval_harness             # Phase-A acceptance gate vs thresholds
```

The eval gate requires, among others: source attribution 100%, prompt-injection
resistance 100%, unsupported-claim rate ≤ 0.10. All currently pass on the synthetic set.

## Repository layout

```
.
├── ROADMAP.md            # phased product, technology & business plan (read this)
├── backend/              # FastAPI + SQLAlchemy service, clinical pipeline, ML, tests
│   └── README.md         # detailed backend docs & API surface
├── frontend/
│   ├── index.html        # self-contained futurist dashboard (no build step)
│   └── next-app/         # Next.js scaffold (not build-verified)
└── docker-compose.yml    # Postgres for local dev
```

## Before any pilot

Real authentication (not headers), database row-level security, consent/authorization
records, OCR of real records, clinician-reviewed terminology, tamper-evident audit
retention, real-data model validation, and a formal CDSCO/DPDP intended-use assessment.
See [ROADMAP.md](ROADMAP.md) for the full sequencing.

## License

Proprietary. Copyright (c) 2026 Naresh Rana — **all rights reserved.** No use, copy,
modification, or distribution is permitted without a separate written agreement. See
[LICENSE](LICENSE).
