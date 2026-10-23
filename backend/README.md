# Longithread — MVP backend

Longitudinal care-coordination prototype from the medical-AI startup blueprint.
It helps a clinic see what has happened to a patient, what follow-up is due, and
which records conflict — **assisting clinicians, never independently diagnosing
or changing treatment.**

> Developer MVP on synthetic data. Not a medical device. Not for patient care.

## What it does today
1. **Ingestion** — authorized document text (PDF/OCR behind a seam) becomes facts.
2. **Extraction** — deterministic, offline extractor proposes candidate facts; an
   LLM adapter sits behind the same interface (optional).
3. **Validation** — every fact is checked for traceable provenance, terminology,
   permitted unit, plausible range, and unambiguous date, or it is **flagged**.
4. **Reconciliation** — same measurement across unit systems collapses; identical
   duplicates are removed; contradictory records are **surfaced, never auto-resolved**.
5. **Follow-up rules** — versioned, clinician-approved protocols create tasks and
   distinguish **RECORD_MISSING** from "never performed". Protocols: `diabetes_v1`,
   `hypertension_v1`, `hypertension_v2`, `ckd_v1`, `chronic_combined_v1`.
6. **Safety** — prompt-injection text is quarantined and never becomes a fact.
7. **Isolation & audit** — every query is tenant-scoped; state changes are logged
   to an append-only audit trail.
8. **AI decision support** — a transparent logistic-regression model turns validated
   signals into a deterioration-risk score with per-factor attribution, provenance
   back to the source document, and **abstention** when data is insufficient. Trained
   and reported on a deterministic **synthetic** cohort; the raw weights and holdout
   metrics are exposed at `/ml/model`, not hidden.
9. **Cohort analytics** — team-level follow-up completion, overdue load, review rate,
   monitoring-gap rate, and HbA1c trend aggregates, derived only from validated data.
10. **Async jobs** — document imports run on a lightweight in-process queue
    (`POST /jobs/import` → `GET /jobs/{id}`), so large batches don't block the API.

## Layout
```
backend/
  schema.sql                 # illustrative Postgres schema
  app/
    main.py                  # FastAPI routes (tenant-scoped)
    service.py               # DB orchestration, dedup, task generation
    models.py / db.py / config.py / schemas.py
    security.py / audit.py   # tenant context + append-only audit
    clinical/                # extractor, validation, conflicts, terminology, pipeline
    rules/engine.py          # versioned care protocols
    ingestion/               # PDF/text ingestion seam
    ml/                      # features, logistic regression, dataset, risk scoring
    analytics/cohort.py      # team-level metrics
    jobs/queue.py            # in-process async job runner
    synthetic/generator.py   # Phase A edge-case dataset + gold labels
  tests/                     # eval harness + unit/integration/security/ml/analytics tests
frontend/
  index.html                 # self-contained futurist dashboard (no build step)
  next-app/                  # Next.js scaffold (not build-verified)
```

## API surface
| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness + product name |
| GET | `/` | serves the dashboard |
| POST/GET | `/patients` | create / list tenant patients |
| POST | `/documents` | synchronous import + extraction pipeline |
| GET | `/patients/{id}/observations` · `/timeline` | persisted facts + chronological view |
| POST | `/patients/{id}/tasks/generate?protocol=` | run an approved protocol |
| GET | `/patients/{id}/tasks` | task queue |
| POST | `/tasks/{id}/review` (header `X-Decision`) | human-in-the-loop decision |
| GET | `/ml/model` | transparent weights + synthetic holdout metrics |
| GET | `/patients/{id}/risk` | decision-support risk + attribution |
| GET | `/analytics/cohort` | team-level aggregates |
| POST | `/jobs/import` · GET `/jobs/{id}` | async document import |

## Run
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git-Bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload            # http://127.0.0.1:8000/health
```
Open `http://127.0.0.1:8000/` for the dashboard. Postgres via Docker:
`docker compose up` from the repo root (uses `DATABASE_URL`).

## Tests & acceptance gate
```bash
pip install fastapi httpx sqlalchemy pydantic pydantic-settings pytest uvicorn
python -m pytest                       # 39 tests
python -m tests.eval_harness           # prints Phase A metrics vs thresholds
```
The eval gate (set **before** results, per the blueprint) requires, among others:
source-attribution 100%, unsupported-claim rate ≤ 0.10, prompt-injection
resistance 100%. All currently pass on the synthetic set.

## Deliberate limits (do before any pilot)
Real authentication (not headers), database row-level security, consent/authorization
records, OCR quality, terminology catalogs reviewed by a clinician, tamper-evident
audit retention, real-data model training/validation, and a formal CDSCO/DPDP
intended-use assessment. The ML risk score is a synthetic-baseline decision aid only —
it does not diagnose, and its accuracy on real patients is unproven.

See `../ROADMAP.md` for the future-ready build-out and business plan.
