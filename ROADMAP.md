# Longithread — Product, Technology & Business Roadmap

> **Longitudinal care-coordination intelligence.** An evidence-backed layer that
> helps clinical teams see what happened to a patient, what follow-up is due, and
> which records conflict — so nothing is lost between visits.

This document turns the medical-AI startup blueprint into a concrete build-and-scale
plan. It is honest about what the current code does and does **not** do. Read the
"Truth about 'perfect, no-error AI'" box first — it governs every claim below.

---

## Truth about "perfect, no-error AI" (non-negotiable)

No one can ship a medical-AI product that provably has "no errors," and no
investor, clinician, or regulator will believe a company that says it does. What we
**can** build — and what actually creates durable value — is a system that:

- is **correct enough to be useful** and **honest about the rest**,
- **never invents clinical facts** (every value traces to a source document),
- **abstains and escalates to a human** when data is thin, ambiguous, or conflicting,
- **measures** its error rates against pre-set thresholds and improves them over time,
- keeps a **human clinician** responsible for every diagnosis and treatment decision.

That combination — provable provenance, forced human oversight, and instrumented
accuracy — is the real moat. "No error" is a marketing dead-end; **"auditable and
safe to oversee"** is a regulatory and commercial asset. Longithread is built as
**clinical decision support**, not an autonomous diagnostician. Nothing here changes
that.

---

## Where the code is today (MVP, verified)

**Status: a working, tested laptop-buildable backend + dashboard. Not a medical device.**

- Pipeline: ingest → extract → validate → reconcile → rules → tasks.
- Safety: prompt-injection quarantine, conflicts *surfaced not auto-resolved*,
  `RECORD_MISSING` distinguished from "never performed", tenant isolation,
  append-only audit trail.
- Protocols: `diabetes_v1`, `hypertension_v1`, `hypertension_v2`, `ckd_v1`,
  `chronic_combined_v1`.
- AI: transparent logistic-regression deterioration risk with factor attribution,
  provenance, and abstention — **trained and reported on synthetic data only**.
- Analytics: cohort follow-up completion, overdue load, monitoring-gap rate,
  HbA1c trend aggregates.
- Async: in-process job queue for batch document import.
- Frontend: self-contained futurist dashboard + a Next.js scaffold (not build-verified).
- Tests: **39 passing**, including a Phase-A eval gate (source attribution 100%,
  unsupported-claim ≤ 0.10, prompt-injection resistance 100%).

**What is NOT real yet:** authentication (headers, not identity), row-level security,
consent records, OCR of actual scanned Indian records, clinician-reviewed terminology,
tamper-evident retention, and **any** real-world accuracy claim. Treat the ML numbers as
a plumbing demo, not evidence.

---

## Product pillars

1. **Reconciliation** — turn messy, duplicated, contradictory, multi-format records
   into one trustworthy, source-linked timeline.
2. **Continuity** — versioned, clinician-approved care protocols that reliably
   surface the *next action* and prove it happened.
3. **Decision support** — risk, trend, and gap signals with attribution and
   abstention — never autonomous calls.
4. **Governance** — provenance, audit, consent, and evaluation as first-class,
   inspectable features (this is what clinics and regulators buy).

---

## Phased roadmap

### Phase 0 — Foundation (DONE, this repo)
Laptop-buildable MVP, eval gate, synthetic ML demo, dashboard. *Exit: the demo above.*

### Phase 1 — Make it real and safe (weeks 1–8)
Goal: a pilot-ready, secure, multi-tenant SaaS. **No new clinical claims.**

- [ ] **Real authN/authZ**: OIDC/SSO, service tokens, RBAC (clinician / coordinator /
      admin), session audit. Retire header-based identity.
- [ ] **Row-level security** in Postgres (`tenant_id` enforced by policy, not app code);
      move SQLite → Postgres everywhere.
- [x] **Consent & authorization records** as first-class tables; every read of a
      patient's data checks a lawful basis. **Done at the app/API layer** (grant/revoke,
      per-purpose, enforced before import and per-patient reads); wire into DPDP
      obligations and move enforcement **into the database** (RLS) as the next step.
- [x] **Tamper-evident audit**: hash-chained, append-only, verifiable chain
      (`GET /audit/verify`). **Done** — editing/deleting/reordering is now detectable;
      still needs DB-level revoke-only append grants + an exportable retention policy.
- [ ] **Real ingestion**: PDF text + OCR seam wired to a vetted OCR engine; multilingual
      (English + Hindi/regional) lab reports; page/section-level provenance.
- [ ] **Terminology mapping**: LOINC/SNOMED subsets + a clinician-owned alias catalog;
      versioned and reviewable, not hardcoded.
- [ ] **LLM extraction behind the existing seam** (optional, feature-flagged): structured
      JSON output, **strict validation**, never allowed to emit an un-sourced fact;
      prompt-injection still quarantined before the model sees the text.
- [ ] **Observability**: structured logs, metrics, tracing, error budgets.
- [ ] **CI/CD**: pytest + eval gate + type checks on every PR; container image; IaC.
- [ ] **Frontend**: replace scaffold with the real Next.js app (typed API client done);
      accessibility pass; loading/empty/error states; per-fact provenance chips.

*Exit criteria:* a security review, a documented intended-use statement, and the eval
gate passing on **licensed real-shaped (de-identified) records** — not just synthetic.

### Phase 2 — Prove value with clinics (months 3–6)
Goal: the blueprint's Phase B/C validation, before scaling engineering.

- [ ] 10–15 discovery interviews (the 7 questions in the blueprint). **Kill or pivot the
      product here if the problem isn't frequent, expensive, and poorly solved.**
- [ ] 2–3 supervised pilots with pre-specified evaluation protocols.
- [ ] Measure: time-to-prepare a review, task accept/edit/reject rate, missed & duplicate
      tasks, clinician review burden, extraction error by document type, performance
      across patient subgroups, and whether follow-up completion actually improves.
- [ ] **Real-data ML** (only if pilots show value): collect clinician-labelled outcomes,
      retrain and **externally validate**; report calibration, discrimination, and
      subgroup performance; keep abstention + attribution mandatory.
- [ ] Regulatory advisory: does the intended function constitute medical-device software
      (CDSCO Medical Device Software guidance)? Classification and evidence plan.

*Exit criteria:* a clinic renews and can name the time/cost saved, plus signed-off
accuracy thresholds on real data.

### Phase 3 — Integrations & depth (months 6–12)
Goal: live inside hospital workflows instead of asking teams to duplicate work.

- [ ] **FHIR/ABDM adapters** (r4 resources) — read/normalise from existing EHRs; do not
      require a rip-and-replace.
- [ ] **HL7 v2 / PDF / portal** ingest for labs and discharge summaries.
- [ ] More protocols + **protocol authoring studio** so clinicians configure, version,
      and approve rules without code (with full audit + test coverage per protocol).
- [ ] **Longitudinal analytics**: cohorts, drift monitoring on model & data, population
      dashboards, care-gap reports.
- [ ] **Alerting & routing**: safe escalation paths, acknowledgement tracking, digest
      queues; anti-alarm-fatigue tuning.
- [ ] **Workflow**: roles, SLAs, task assignment, mobile review queue.

### Phase 4 — Platform & scale (year 2+)
Goal: a vendor-neutral longitudinal-care infrastructure layer, expansion-ready.

- [ ] Multi-region deployment, data residency (DPDP / GDPR-adjacent regimes).
- [ ] Per-tenant model & protocol governance; formal change control.
- [ ] Continuous-evaluation platform: golden datasets, regression gates, drift alarms —
      accuracy is a monitored metric, forever, not a one-time launch check.
- [ ] Interoperability certifications and an integration marketplace.
- [ ] Additional chronic conditions and care settings; regulatory filings per geography
      (FDA SaMD assessment if/when a function becomes regulated).

---

## Future-ready technical architecture

```
Frontend            Next.js + TypeScript (typed client done) → real app, design system
API / identity      FastAPI + OIDC + RBAC  · tenant + consent enforcement at the edge
Ingestion           PDF/OCR seam · FHIR/HL7 adapters · multilingual · page-level provenance
Clinical data layer LOINC/SNOMED mapping · validation · conflict surfacing · unit reconcile
Intelligence layer  versioned rules engine · optional LLM extraction (gated) ·
                    transparent ML (risk/trend/gap) with attribution + abstention
Analytics           cohort + longitudinal + drift + continuous-eval metrics
Persistence         PostgreSQL + RLS · hash-chained audit · encrypted object store
Async/scale         durable queue (Celery/worker) replacing in-process runner ·
                    background ingest, schedulers, idempotent jobs
Platform            containers + IaC + CI/CD · observability · feature flags · multi-region
```

Principles that do **not** change as we scale: no invented clinical values; every fact
carries provenance; conflicts are surfaced for humans, never silently resolved; every
AI output is decision support under clinician oversight; accuracy is measured against
thresholds set **before** seeing results.

---

## Data-analysis & AI roadmap (honest sequencing)

1. **Now (synthetic):** logistic-regression risk demo, cohort analytics — plumbing proof.
2. **Phase 2 (real, validated):** outcome-labelled data → retrain → external validation
   → calibration + subgroup reports. Only then does a model inform clinical review.
3. **Phase 3 (breadth):** trend/monitoring-gap detection, deterioration signals per
   condition, care-gap analytics.
4. **Phase 4 (platform):** continuous evaluation, drift control, model governance.

Guardrails for every ML feature: provenance, attribution, **abstention**, thresholds,
and a human in the loop. We do not build an autonomous diagnostician, and we do not
market one.

---

## Business model toward scale

**Positioning:** sell *workflow outcomes and governance* (fewer missed follow-ups,
reconciled records, auditability), **not** "AI summaries" — summaries are a crowded,
weakly differentiated commodity. The wedge is reliable cross-visit reconciliation plus
measurable completion of clinician-approved follow-ups.

**Who pays (in order):** private chronic-care clinics & polyclinics → diagnostic/lab
networks → multi-site hospital groups & teleradiology/imaging ops → population-health
programs / payers. Hospital imaging and enterprise EHR sales cycles are slow; start
where a workflow outcome is visible in a quarter.

**Pricing:** per-active-patient or per-clinician-seat SaaS tiers, with an
integration/setup tier and an analytics/governance add-on. Land small, expand by site.

**Motion:** design-partner pilots → case studies with measured time/cost saved →
referred clinic clusters → regional rollups → platform/API ecosystem.

**Moat (compounding):** validated workflow performance, data-reconciliation
reliability, integration breadth, clinical protocol library + governance, and trust
earned through audited real deployments — **not** a single model.

**Unit economics to target:** gross margin ≥ 70% at scale (software, not services);
payback on a clinic < 2 quarters once follow-up-time savings are proven; churn anchored
to switching cost of reconciled history + integrations.

**Talent arc:** founder-eng + contract clinician (Ph0–1) → + security/DB, + frontend,
+ clinical-ops (Ph1–2) → + ML/data, + regulatory/QA, + sales (Ph2–3) → platform & GTM
org (Ph4). Keep a named clinical lead and a governance owner before the first pilot.

---

## Regulatory & compliance track (India-first, expansion-aware)

- **Medical-device software:** CDSCO — Medical Devices Rules 2017 and the July 2026
  Medical Device Software guidance. Get an intended-use classification opinion
  **before** launch; document intended use precisely.
- **Data protection:** DPDP Rules 2025 (phased commencement from Nov 2025) — consent &
  lawful processing, purpose limitation, minimisation, access logging, retention &
  deletion, breach response, processor contracts, built in from the start.
- **Interoperability:** ABDM standards/participation; FHIR helps technically but grants
  **no** record access or reuse-for-training rights.
- **Expansion:** FDA SaMD assessment if a function becomes regulated; per-country
  privacy + device + clinical-evidence rules; WHO AI-in-health governance (human
  oversight, safety, equity).
- **North star:** keep the first product on record organisation + clinician-approved
  workflow support, and never assume that framing auto-exempts it from device
  regulation — get the opinion on paper.

---

## Key risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Crowded adjacent market (Eka Care, HealthPlix, etc.) | Differentiate on reconciliation + audited follow-up completion, not AI summaries; validate before building |
| Clinics won't pay for a coordination layer | Discovery interviews + priced pilots + measured time/cost savings before Phase 3 spend |
| Data access / privacy | Consent-as-data, RLS, DPDP controls, de-identified pilots, security review |
| "AI that's wrong" erodes trust | Provenance + surfacing + abstention + pre-set accuracy gates + human oversight |
| Regulatory surprise | Early CDSCO intended-use opinion; decision-support framing documented |
| Overclaiming "no error" | This roadmap's opening rule; every metric is measured and disclosed |
| LLM wrappers commoditise us | Our value is governance + reconciliation + workflow, not a chatbot |

---

## What "done" looks like at each gate

- **P1:** secure multi-tenant SaaS, real ingestion, eval gate passes on de-identified
  real-shaped data, security review + intended-use statement.
- **P2:** a clinic renews because measured follow-up/time savings are real; accuracy
  thresholds signed off on real data.
- **P3:** Longithread lives inside existing systems (FHIR/EHR) with self-service,
  tested protocols and drift monitoring.
- **P4:** a vendor-neutral, multi-region longitudinal-care layer whose moat is provable
  trust — audited accuracy, provenance, and governance — deployed across care settings.

Every gate is a **stop/go decision based on evidence**, not a feature count. If a gate's
evidence is weak, we change the product or the segment before scaling engineering or
hype.
