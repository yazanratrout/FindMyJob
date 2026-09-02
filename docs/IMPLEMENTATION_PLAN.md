# FindMyJob — Implementation Plan

A local, single‑user, human‑in‑the‑loop pipeline that finds working‑student ("Werkstudent") and
related student positions in a chosen city, analyzes each one, scores how well it fits your
profile, and — on your explicit click — drafts a tailored cover letter you download as a `.docx`
and submit yourself.

**This document is the build spec.** It is organized into checkpoints. Each checkpoint is
independently shippable, has a concrete deliverable and acceptance criteria, and builds on the
previous one. Do them in order.

---

## 0. Product summary

### 0.1 What it does

1. You upload your documents (CV, Immatrikulationsbescheinigung, Transcript/Notenspiegel,
   reference letters) and set your preferences once, in a web UI. Everything is saved.
2. Every morning at a time you choose, a pipeline runs:
   - queries a set of **allowlisted** job APIs and public company career endpoints,
   - deduplicates against everything seen before,
   - extracts structured facts from each posting with an LLM,
   - computes a 0–100 match score using hard limits (disqualifiers) and soft limits (score
     penalties),
   - decides "recommend / maybe / archive" against your threshold,
   - works out which of your documents each posting needs.
3. The web UI shows recommended jobs, highest score first. Open one to see the analysis, the
   score breakdown ("why this number"), the original description, the apply link, and a
   documents checklist.
4. If, after reading it yourself, you like it, you click **Prepare cover letter**. An LLM drafts
   one tailored to that posting and your profile. You edit it inline, then download
   `Cover letter {Company}.docx` and finish/submit it yourself.
5. A lightweight tracker records status per job (interested → applied → interview → outcome) with
   follow‑up reminders.

### 0.2 Explicit non‑goals

- **No automated submission.** The pipeline ends at "application package assembled." You submit.
- **No scraping of sites that forbid it** (LinkedIn, StepStone, Indeed, Xing). Not scaffolded.
- **Not multi‑user / not a SaaS.** One person, one machine, `localhost` only.
- **No storage or redistribution of scraped datasets.** Postings are cached locally for your
  personal review only and pruned on a schedule.

### 0.3 Principles

- **Allowlist sourcing.** A source is added only if it offers an official API, a documented
  public endpoint, or an explicitly public feed, and its terms permit personal automated access.
- **Cheap before expensive.** Deterministic filters run before any LLM call. LLM output is cached
  by content hash. A monthly token budget is enforced.
- **Everything visible.** Scores show their components. Extracted facts link back to the source
  text. The cover letter lists which profile facts it used, so you can catch fabrication.
- **Human gates where they matter.** The system recommends; you decide to apply; you trigger and
  review the cover letter; you submit.
- **Pluggable sources.** Every job source implements one interface. Adding/removing one touches
  no other code.

---

## 1. Architecture

### 1.1 Component diagram

```
                         ┌─────────────────────────────────────────────┐
                         │                Web UI (React)               │
                         │  Onboarding · Dashboard · Job detail ·       │
                         │  Cover letter editor · Tracker · Settings    │
                         └───────────────┬─────────────────────────────┘
                                         │ REST (localhost)
                         ┌───────────────▼─────────────────────────────┐
                         │              FastAPI backend                │
                         │                                             │
  ┌───────────┐   cron   │  ┌────────────────────────────────────────┐ │
  │ Scheduler ├──────────┼─▶│          Pipeline orchestrator         │ │
  │(APSchedul.)│  "Run now"│ │  fetch → normalize → enrich → dedup →  │ │
  └───────────┘   (button) │ │  analyze → score → judge → decide →    │ │
                         │  │  documents                             │ │
                         │  └───┬──────────┬──────────┬──────────────┘ │
                         │      │          │          │                │
                         │  ┌───▼───┐  ┌───▼────┐  ┌──▼─────┐          │
                         │  │Sources│  │  LLM   │  │Embed.  │          │
                         │  │registry│ │(Claude)│  │(local  │          │
                         │  │        │ │        │  │ MiniLM)│          │
                         │  └───┬───┘  └────────┘  └────────┘          │
                         │      │                                      │
                         │  ┌───▼──────────────────────────────────┐   │
                         │  │ API connectors │ ATS connectors      │   │
                         │  │ BA · Adzuna ·  │ Greenhouse · Lever ·│   │
                         │  │ Arbeitnow ·    │ Personio ·          │   │
                         │  │ The Muse       │ SmartRecruiters ·   │   │
                         │  │                │ Ashby · JobPosting  │   │
                         │  │                │ JSON-LD             │   │
                         │  └────────────────────────────────────────┘ │
                         │                                             │
                         │  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
                         │  │Notifier  │  │Cost meter│  │Eligibility│  │
                         │  │email/TG  │  │+ budget  │  │(optional) │  │
                         │  └──────────┘  └──────────┘  └───────────┘  │
                         └───────────────┬─────────────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │ SQLite (SQLModel + Alembic)              │
                    │ Files: uploaded docs, generated .docx,   │
                    │ MiniLM model cache                       │
                    └─────────────────────────────────────────┘
```

### 1.2 Data flow (one daily run)

1. **Scheduler** fires at `run_time` in `run_timezone`; creates a `Run` row (`status=running`).
2. **Fetch:** for each configured & enabled source, build a `SourceQuery` from Settings and call
   `source.fetch()`. Each returns `RawJob[]`. Source failures are caught, logged into
   `run.errors_json`, and do not abort the run.
3. **Normalize:** map every `RawJob` to a canonical shape; resolve/attach `Company`.
4. **Enrich:** for jobs missing a full description, fetch the posting URL (robots‑aware) and
   extract main content; also parse any `JobPosting` JSON‑LD.
5. **Dedup:** compute canonical key + content hash + embedding. New unique jobs get a `Job` row;
   repeats update `last_seen_at` and link to their canonical `Job`.
6. **Pre‑filter (no LLM):** apply deterministic hard filters and a cheap title/keyword relevance
   gate. Jobs that fail hard filters get a `JobScore` with `decision=archived` and are not sent
   to the LLM.
7. **Analyze (LLM, cached):** for each surviving job without a current `JobAnalysis`, run the
   analyzer prompt → structured JSON.
8. **Score:** deterministic soft score from `JobAnalysis` + Profile + Settings weights.
9. **Judge (LLM):** holistic fit 0–100 + rationale + missing qualifications + strengths.
10. **Decide:** `final_score = blend(soft, judge)`; bucket into recommend / maybe / archive;
    compute documents checklist.
11. **Budget guard:** if the monthly token budget is hit mid‑run, remaining jobs are left
    unanalyzed and picked up next run.
12. **Finish:** `Run` gets `status=completed`, stats, token/cost totals.
13. **Notify:** send the digest (top N new recommendations) on configured channels.

---

## 2. Tech stack

### 2.1 Backend

| Concern | Choice |
|---|---|
| Language / runtime | Python 3.12 |
| Web framework | FastAPI + Uvicorn |
| ORM / models | SQLModel (SQLAlchemy 2 + Pydantic) |
| Migrations | Alembic |
| Scheduling | APScheduler (in‑process), plus a macOS `launchd` trigger for reliability |
| HTTP client | `httpx` (async) + `tenacity` (retry/backoff) |
| HTML extraction | `trafilatura` (main content) + `selectolax` (JSON‑LD, targeted parsing) |
| robots.txt | `urllib.robotparser` wrapped with caching |
| LLM | `anthropic` SDK — Claude. Haiku for extraction, Sonnet for judge + cover letter |
| Embeddings | `sentence-transformers`, model `paraphrase-multilingual-MiniLM-L12-v2` (local, free, DE+EN) |
| Vector search | brute‑force cosine in NumPy over the candidate set (dataset is small); no vector DB |
| DOCX | `docxtpl` (Jinja‑in‑Word template) + `python-docx` for post‑tweaks |
| Config | `pydantic-settings` for secrets (`.env`); mutable settings live in the DB |
| Logging | `structlog` (JSON logs to file + pretty to console) |
| Auth | single passphrase, Argon2 hash, signed session cookie; server binds `127.0.0.1` |
| Tests | `pytest`, `pytest-asyncio`, `respx` (mock httpx), `syrupy` (snapshot LLM‑shaped fixtures) |
| Lint / type | `ruff`, `mypy` |
| Task runner | `just` (or `make`) |

### 2.2 Frontend

| Concern | Choice |
|---|---|
| Framework | React 18 + Vite + TypeScript |
| Styling | TailwindCSS |
| Components | shadcn/ui (Radix under the hood) |
| Server state | TanStack Query |
| Routing | React Router |
| Forms / validation | React Hook Form + Zod |
| Charts (score breakdown) | Recharts |

### 2.3 Storage layout

```
~/Library/Application Support/FindMyJob/     (macOS app data dir; overridable via env)
  findmyjob.db                 SQLite
  documents/<profile_id>/...    uploaded CV, enrollment cert, transcript, references
  letters/<job_id>/...          generated cover-letter .docx + versions
  models/                       cached MiniLM weights
  logs/findmyjob.log
```

Project repo (`/Users/yazan/Desktop/FindMyJob`):

```
FindMyJob/
  docs/IMPLEMENTATION_PLAN.md
  backend/
    app/
      main.py            FastAPI app factory, router mounting, static frontend serving
      config.py          pydantic-settings (secrets, paths)
      db.py              engine, session, init
      models/            SQLModel tables (one file per aggregate)
      schemas/           request/response Pydantic models
      api/routes/        profile.py documents.py settings.py jobs.py runs.py
                         cover_letters.py applications.py eligibility.py health.py
      sources/
        base.py          JobSource ABC, SourceQuery, RawJob
        registry.py      discovery + enable/disable from Settings
        api/             ba.py adzuna.py arbeitnow.py themuse.py
        ats/             greenhouse.py lever.py personio.py smartrecruiters.py ashby.py
        jsonld.py        schema.org JobPosting extractor (career pages)
        companies.yaml   curated employer registry (name, ats_type, slug, careers_url, city)
      pipeline/
        orchestrator.py  run() — the 13-step flow
        normalize.py
        enrich.py        robots-aware fetch + trafilatura + jsonld merge
        dedup.py         canonical key, content hash, embedding similarity
        analyze.py       calls llm.analyzer, handles cache + versioning
        score.py         hard filters + soft score + weights
        judge.py         calls llm.judge, blends, decides
        documents.py     documents-needed checklist logic
        prefilter.py     cheap deterministic gate before LLM
      llm/
        client.py        Anthropic wrapper: model routing, retries, token accounting, cache
        prompts/         *.md prompt templates
        profile_parser.py
        analyzer.py
        judge.py
        cover_letter.py
      services/
        profile.py settings.py notifications.py eligibility.py cost.py embeddings.py
      docx/
        template.docx    DIN 5008 (Form B) cover-letter template with Jinja fields
        render.py
      scheduler.py       APScheduler setup, job registration from Settings
    tests/
    alembic/
    pyproject.toml
  frontend/
    src/
      pages/ Onboarding.tsx Dashboard.tsx JobDetail.tsx CoverLetter.tsx Tracker.tsx Settings.tsx Runs.tsx
      components/
      api/ client.ts hooks.ts
      lib/
    package.json
  deploy/
    com.findmyjob.daily.plist       launchd trigger
    com.findmyjob.server.plist      launchd always-on server (optional)
  .env.example
  justfile
  README.md
```

---

## 3. Data model

SQLite via SQLModel. Timestamps are UTC. JSON columns hold structured sub‑objects that are never
queried relationally.

### 3.1 Tables

**profile** — one row (single user)
`id · full_name · email · phone · street · postal_code · city · country · nationality ·
is_eu_eea (bool) · university · program · degree_level (bachelor|master|phd) ·
current_semester · enrollment_valid_until (date) · expected_graduation (date) ·
cv_document_id (fk) · structured_json (parsed CV) · voice_sample_text · created_at · updated_at`

**profile_skill**
`id · profile_id (fk) · name · category (language|technical|tool|domain|soft) · proficiency
(1–5) · years (float, nullable) · source (cv|manual|transcript)`

**document**
`id · profile_id (fk) · type (cv|enrollment|transcript|reference|portfolio|other) · filename ·
stored_path · mime · size_bytes · parsed_json (nullable) · parse_status
(pending|done|failed) · uploaded_at`

**settings** — one row, JSON‑heavy
`id · target_city · target_lat · target_lon · radius_km · allow_remote (bool) ·
target_fields (json[str]) · target_titles (json[str]) · keywords_allow (json[str]) ·
keywords_block (json[str]) · job_types (json: werkstudent|praktikum|thesis|minijob|
student_assistant) · recency_days · language_max_cefr (A1..C2|native) · language_hard (bool) ·
hours_max · hours_hard (bool) · contract_types (json[str]) · contract_type_hard (bool) ·
score_threshold_recommend (default 70) · score_threshold_maybe (default 55) ·
weights_json · blend_soft_ratio (default 0.6) · run_time (HH:MM) · run_timezone
(default Europe/Berlin) · notify_channels (json) · notify_email · notify_telegram_chat_id ·
monthly_token_budget · cover_letter_language_mode (match_posting|always_de|always_en) ·
cover_letter_tone (formal|semi_formal) · eligibility_module_enabled (bool) ·
sources_enabled (json map key→bool) · updated_at`

**company**
`id · name · normalized_name · ats_type (greenhouse|lever|personio|smartrecruiters|ashby|
none) · ats_slug (nullable) · careers_url (nullable) · city (nullable) · is_favorite (bool) ·
is_active (bool) · added_by (seed|user|discovered) · created_at`

**run**
`id · trigger (schedule|manual) · started_at · finished_at · status (running|completed|failed) ·
stats_json (found, enriched, new, duplicates, prefilter_passed, analyzed, recommended, maybe,
archived) · input_tokens · output_tokens · cost_eur · errors_json (list of {source, error}) ·
budget_exhausted (bool)`

**job**
`id · canonical_job_id (fk self, null = is canonical) · source_key · source_job_id · url ·
apply_url · title · normalized_title · company_id (fk) · company_name_raw · location_raw ·
is_remote (bool) · posted_at (nullable) · first_seen_run_id (fk) · last_seen_at ·
lifecycle (active|stale|dead) · raw_json · jd_text · jd_content_hash · salary_raw ·
created_at`
Unique: `(source_key, source_job_id)`.

**job_embedding**
`job_id (pk, fk) · vector (blob: float32[384]) · model_version`

**job_analysis**
`id · job_id (fk) · analyzer_version · must_haves (json[str]) · nice_haves (json[str]) ·
skills (json: [{name, required (bool)}]) · languages (json: [{lang, cefr, required}]) ·
weekly_hours (int, nullable) · weekly_hours_basis (stated|inferred|unknown) ·
contract_type (werkstudent|praktikum|thesis|minijob|part_time|full_time|unknown) ·
salary_min · salary_max · salary_currency · salary_period (hour|month|year) ·
start_date_text · deadline (nullable) · enrollment_required (yes|no|unknown) ·
english_only (bool) · application_method (ats_form|email|external|unknown) ·
documents_requested (json[str]) · seniority (student|entry|junior|mid|unknown) ·
location_resolved (json: {lat, lon, city}) · red_flags (json[str]) ·
source_snippets (json map field→quoted text) · raw_json · created_at`
Unique: `(job_id, analyzer_version)`.

**job_score**
`id · job_id (fk) · run_id (fk) · hard_pass (bool) · hard_failures (json[str]) ·
soft_score (0–100) · soft_breakdown_json (component→{raw, weight, contribution}) ·
llm_holistic (0–100, nullable) · llm_rationale · missing_qualifications (json[str]) ·
strengths_to_highlight (json[str]) · final_score (0–100) ·
decision (recommended|maybe|archived) · documents_needed (json: [{doc_type, necessity
(required|likely|optional), reason}]) · created_at`
Latest row per `job_id` is the current verdict.

**application**
`id · job_id (fk) · status (interested|preparing|applied|interview|offer|rejected|withdrawn) ·
applied_at (nullable) · follow_up_at (nullable) · outcome_note · documents_used (json[str]) ·
created_at · updated_at`

**cover_letter**
`id · job_id (fk) · application_id (fk, nullable) · version · language · tone ·
content_json (subject, recipient_block, salutation, paragraphs[], closing) ·
claims_used (json: [{claim, evidence_from_profile}]) · docx_path · user_edited (bool) ·
created_at`

**eligibility_ledger** — only if module enabled
`id · profile_id (fk) · period_start (date) · period_end (date) · day_type (full|half) ·
day_count (computed) · job_id (fk, nullable) · note · created_at`

**semester_calendar** — supports the 20h rule + non‑EU day counting
`id · profile_id (fk) · term_label · lecture_start (date) · lecture_end (date) ·
break (bool derived)`

**llm_call_log**
`id · run_id (fk, nullable) · purpose (profile_parse|analyze|judge|cover_letter|keyword_suggest)
· model · input_tokens · output_tokens · cost_eur · cache_hit (bool) · created_at`

**app_auth** — one row
`id · passphrase_hash · created_at`

### 3.2 Derived / cached values

- `normalized_name`, `normalized_title`: lowercase, strip legal suffixes (GmbH, AG, SE, e.V.),
  collapse whitespace, transliterate umlauts, drop `(m/w/d)` / `(f/m/x)` markers.
- `jd_content_hash`: SHA‑256 of normalized JD text — the LLM cache key.

---

## 4. Sourcing policy (must read before CP5)

### 4.1 Allowlist

| Source | Access | Auth | Notes |
|---|---|---|---|
| Bundesagentur für Arbeit — Jobsuche API | Official public REST API | API key (client credentials) | Largest German coverage incl. Werkstudent; geo + radius search built in |
| Adzuna API | Official API, free tier | `app_id` + `app_key` | `country=de`; supports `where`, `distance`, `max_days_old`, salary data |
| Arbeitnow Job Board API | Documented public JSON API | none | Germany‑focused; cursor‑paginated; visa/remote flags |
| The Muse API | Official API | free key | International; good for English‑speaking employers in Munich |
| Greenhouse Job Board API | Public boards API | none | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` |
| Lever Postings API | Public | none | `api.lever.co/v0/postings/{slug}?mode=json` |
| Personio | Public XML job feed | none | `{slug}.jobs.personio.de/xml` |
| SmartRecruiters Posting API | Public | none | `api.smartrecruiters.com/v1/companies/{slug}/postings` |
| Ashby Job Posting API | Public | none | `api.ashbyhq.com/posting-api/job-board/{slug}` |
| schema.org `JobPosting` JSON‑LD | Read from career pages we may visit | none | Only pages allowed by `robots.txt`; used to enrich, not to crawl broadly |

### 4.2 Rules baked into the fetch layer

- **robots.txt** is fetched and cached per host; any page fetch that it disallows is skipped.
- **User‑Agent** identifies the tool and includes a contact: `FindMyJob/1.0 (personal job search; +mailto:<your email>)`.
- **Rate limiting:** per‑host token bucket, default 1 request / 2 s, configurable; exponential
  backoff on 429/503.
- **No pagination beyond need:** stop once results exceed `recency_days` or a per‑source cap.
- **Personal use only:** postings are cached for your review; a retention job deletes archived
  jobs older than `N` days (default 90) and their analyses.
- **Excluded, not scaffolded:** LinkedIn, StepStone, Indeed, Xing, Glassdoor. If broader coverage
  is wanted later, add a paid aggregator (e.g. an official Google Jobs API reseller) as one more
  `JobSource` — no other code changes.

### 4.3 Company registry (`companies.yaml`)

Seed ~40 Munich employers likely to hire students, each with `ats_type` + `slug` where a public
endpoint exists. Users add/disable companies in Settings. The pipeline queries each active
company's ATS directly for student‑type roles.

---

## 5. Checkpoints

Effort is in **sessions** (≈ half a day). These are rough.

> **Definition of done for every checkpoint:** code + tests green, `ruff`/`mypy` clean, the
> deliverable demoable, a one‑paragraph note in `docs/CHANGELOG.md`.

---

### CP0 — Repo scaffold & tooling — *1 session*

**Goal:** a running empty app on both sides.

**Build**
- `backend/pyproject.toml` with deps from §2.1; `just` targets: `dev`, `test`, `lint`,
  `typecheck`, `migrate`, `run-pipeline`.
- FastAPI app factory in `app/main.py`; `GET /api/health` returns `{status, version, db_ok}`.
- `frontend/` via Vite React‑TS; Tailwind + shadcn init; a Dashboard placeholder that calls
  `/api/health`.
- `.env.example` with every secret key documented.
- `structlog` configured; logs to `logs/findmyjob.log` + console.
- `.gitignore` excludes `data/`, `.env`, `letters/`, `__pycache__`, `node_modules`.

**Acceptance:** `just dev` serves API on `127.0.0.1:8000` and UI on `5173`; the placeholder shows
"db_ok: true".

---

### CP1 — Config, DB, migrations — *1 session*

**Goal:** persistence foundation.

**Build**
- `config.py`: resolves the app‑data dir (env override `FINDMYJOB_DATA_DIR`), creates
  subfolders, loads secrets.
- `db.py`: engine, `get_session` dependency, `init_db()`.
- All SQLModel tables from §3 (no logic yet).
- Alembic wired; initial migration.
- Seed routine: inserts the singleton `settings` row with defaults and loads `companies.yaml`
  into `company`.

**Acceptance:** `just migrate` builds the schema; a `pytest` fixture spins an in‑memory DB;
`GET /api/settings` returns defaults.

---

### CP2 — Document intake & storage — *1 session*

**Goal:** upload and manage the four document types.

**Build**
- `POST /api/documents` (multipart): validates type ∈ enum, mime ∈ {pdf, docx, png, jpg}, size ≤
  15 MB; stores under `documents/<profile_id>/<uuid>.<ext>`; creates `document` row
  (`parse_status=pending`).
- `GET /api/documents`, `GET /api/documents/{id}/file`, `DELETE /api/documents/{id}`.
- Text extraction utility: `pdfplumber` for PDF, `python-docx` for DOCX, Claude vision fallback
  for image‑only PDFs/scans (flagged, costs tokens).
- Frontend: a documents panel (drag‑drop, list, replace, delete).

**Acceptance:** upload a PDF CV → row created, file on disk, raw text extractable in a unit test.

---

### CP3 — Profile builder (LLM) — *2 sessions*

**Goal:** turn documents into a structured, editable profile.

**Build**
- `llm/profile_parser.py` + `prompts/profile_parser.md`. Input: CV text (+ transcript,
  enrollment cert, references text if present). Output JSON:
  ```json
  {
    "full_name": "", "email": "", "phone": "", "address": {...},
    "nationality": "", "university": "", "program": "", "degree_level": "master",
    "current_semester": 3, "enrollment_valid_until": "2026-03-31",
    "expected_graduation": "2027-09-30",
    "skills": [{"name": "Python", "category": "technical", "proficiency": 4, "years": 3, "evidence": "quote from CV"}],
    "languages": [{"lang": "German", "cefr": "B2"}, {"lang": "English", "cefr": "C1"}],
    "work_history": [{"title": "", "org": "", "start": "", "end": "", "bullets": []}],
    "projects": [...], "education": [...],
    "highlights_from_references": ["quotable strength ..."]
  }
  ```
- `services/profile.py`: merge parser output into `profile` + `profile_skill`; never overwrite
  fields the user has manually edited (track an `is_user_edited` set per field).
- Endpoints: `POST /api/profile/parse` (runs parser over current docs),
  `GET/PUT /api/profile`, `PUT /api/profile/skills`.
- `voice_sample_text`: a textarea where the user pastes a cover letter they wrote themselves;
  stored verbatim for later few‑shot use.
- Frontend: profile review screen — editable fields, skills table with proficiency sliders, a
  "re‑parse from documents" button that diffs and asks before applying.

**Acceptance:** upload real CV → parse → profile screen populated; edit a field → re‑parse does
not clobber it.

---

### CP4 — Settings & onboarding backend — *1 session*

**Goal:** all preferences persisted and validated.

**Build**
- `GET/PUT /api/settings` with a Zod‑equivalent Pydantic model covering every field in §3.1
  `settings`.
- City → coordinates via a one‑shot geocode (Nominatim, cached; respect its usage policy: 1 req/s,
  UA set). Store `target_lat/lon`.
- `POST /api/settings/suggest-keywords`: LLM takes `target_fields` + profile skills + a few
  sample job titles and returns ~30 candidate keywords grouped as
  `{core, adjacent, tools, likely_noise}`. The UI lets the user move each into allow / block /
  ignore. Result saved to `keywords_allow` / `keywords_block`.
- `semester_calendar` CRUD (term label + lecture start/end); used by the eligibility module and
  by "is this posting's hours limit realistic during term" checks.

**Acceptance:** PUT invalid settings → 422 with field errors; keyword suggestion returns grouped
list; saved settings survive restart.

---

### CP5 — Source framework + API connectors — *3 sessions*

**Goal:** pull normalized jobs from the four API sources.

**Build**
- `sources/base.py`:
  ```python
  class SourceQuery(BaseModel):
      keywords: list[str]
      city: str; lat: float; lon: float; radius_km: int
      allow_remote: bool
      max_age_days: int
      job_types: list[str]
      limit_per_source: int = 150

  class RawJob(BaseModel):
      source_key: str
      source_job_id: str
      url: str
      apply_url: str | None
      title: str
      company_name: str
      location: str | None
      is_remote: bool = False
      posted_at: datetime | None
      description_text: str | None
      description_html: str | None
      salary_raw: str | None
      extra: dict = {}

  class JobSource(ABC):
      key: str
      display_name: str
      required_secrets: list[str]
      def is_configured(self, secrets) -> bool: ...
      async def fetch(self, q: SourceQuery) -> list[RawJob]: ...
  ```
- `sources/registry.py`: auto‑discovers `JobSource` subclasses, filters by
  `settings.sources_enabled` and `is_configured`.
- Connectors: `ba.py`, `adzuna.py`, `arbeitnow.py`, `themuse.py`. Each maps its native response
  to `RawJob`, translates `job_types` to that API's filter vocabulary (e.g. BA
  `angebotsart`/`arbeitszeit`, Adzuna `contract_time=part_time`), and paginates only until
  `max_age_days` is exceeded.
- Shared HTTP layer in `services/http.py`: async client, per‑host rate limiter, retry policy,
  the standard UA.
- `GET /api/sources` — list with configured/enabled status; `PUT /api/sources/{key}` — toggle.

**Tests:** `respx` fixtures with recorded JSON samples per source; assert `RawJob` mapping,
date filtering, and job‑type translation.

**Acceptance:** `just run-pipeline --fetch-only` prints a table: source → count fetched, with real
credentials in `.env`.

---

### CP6 — ATS connectors + company registry — *2 sessions*

**Goal:** query curated employers' public job endpoints directly.

**Build**
- `sources/ats/greenhouse.py`, `lever.py`, `personio.py`, `smartrecruiters.py`, `ashby.py`.
  Each takes the set of `company` rows whose `ats_type` matches and fetches their postings,
  client‑side filtering to student‑type roles by title/keywords and to the target city.
- Registered as one meta‑source `key="ats"` that fans out over companies, or as one source per
  ATS — implementation detail; pick per‑ATS for cleaner errors.
- `sources/jsonld.py`: given a `company.careers_url` with no known ATS, fetch (robots‑aware) and
  extract `JobPosting` JSON‑LD entries → `RawJob`.
- `companies.yaml` seeded (~40 Munich employers). `GET/POST/DELETE /api/companies`,
  `PUT /api/companies/{id}` (favorite/active). A helper endpoint `POST /api/companies/detect`
  takes a careers URL and guesses `ats_type` + `slug`.

**Acceptance:** for ≥ 5 seeded companies, the connector returns current student roles; unknown‑ATS
company with JSON‑LD yields jobs; a dead slug logs an error without failing the run.

---

### CP7 — Normalization & enrichment — *2 sessions*

**Goal:** consistent job records with full descriptions.

**Build**
- `pipeline/normalize.py`: `RawJob` → fields for a `job` row; company resolution (match
  `normalized_name`, else create `company` with `added_by=discovered`); location parsing;
  `normalized_title`.
- `pipeline/enrich.py`: if `description_text` is missing or < 400 chars, fetch `url`
  (robots‑aware, rate‑limited), run `trafilatura` for main text, merge any JSON‑LD fields
  (hours, salary, dates, `directApply`). Set `jd_text`, `jd_content_hash`, `salary_raw`.
- Mark `lifecycle=dead` when a previously seen job's URL 404s during a later run.

**Acceptance:** a job that arrived as a stub link ends with ≥ 400 chars of clean `jd_text`;
robots‑disallowed host is skipped and logged.

---

### CP8 — Deduplication — *2 sessions*

**Goal:** never show the same position twice.

**Build**
- `services/embeddings.py`: lazy‑load MiniLM; `embed(texts) -> np.ndarray`; cache model in the
  data dir.
- `pipeline/dedup.py`, three tiers:
  1. **Exact:** same `(source_key, source_job_id)` → update `last_seen_at`, done.
  2. **Canonical key:** `normalized_company + "|" + normalized_title + "|" + city`. Match →
     link as duplicate of the existing canonical `job`, keep whichever URL is a direct apply
     link.
  3. **Semantic:** cosine similarity of `embed(title + "\n" + jd_text[:2000])` against canonical
     jobs from the last `recency_days + 14` days for the same company; ≥ `0.92` (configurable) →
     duplicate.
- Reposts: if a canonical job was last seen > `repost_days` (default 21) ago and reappears,
  treat as **new** (companies re‑list stale roles) and reset its scoring.
- Store the vector in `job_embedding`.

**Tests:** fixtures with (a) identical cross‑source postings, (b) same role different wording,
(c) genuinely different roles at one company → assert correct linking.

**Acceptance:** run the pipeline twice back‑to‑back; second run adds 0 new jobs, updates
`last_seen_at` on all.

---

### CP9 — LLM job analyzer — *2 sessions*

**Goal:** structured facts from each posting.

**Build**
- `llm/analyzer.py` + `prompts/analyzer.md`. Model: Haiku. Input: `jd_text`, `title`,
  `company_name`, plus the target city for location resolution. **Output JSON = `job_analysis`
  fields** (§3.1), including `source_snippets` — for every extracted constraint, the verbatim
  sentence it came from (provenance; also lets the UI highlight).
- Strict output handling: request JSON, validate against a Pydantic model, one repair retry on
  failure, else store `raw_json` with `analyzer_version` and a `parse_failed` flag.
- `analyzer_version` constant; bumping it invalidates the cache and re‑analyzes on next run.
- `pipeline/analyze.py`: cache lookup by `jd_content_hash` + `analyzer_version` (across jobs —
  identical text analyzed once); writes `job_analysis`; logs tokens to `llm_call_log`.

**Acceptance:** 10 hand‑picked real postings → analyses spot‑checked; every non‑null constraint
has a matching snippet; identical JD text hits cache on the second job.

---

### CP10 — Scoring engine — *3 sessions*

**Goal:** deterministic, explainable soft score + hard filters.

**Build — `pipeline/prefilter.py` (hard filters):** a job is disqualified (→ `hard_pass=false`,
recorded `hard_failures`) if, **and only if the matching constraint is marked hard in Settings**:

| Constraint | Hard rule |
|---|---|
| Location | resolved job location > `radius_km` from target and not (`allow_remote` and job is remote) |
| Weekly hours | `hours_hard` and `job_analysis.weekly_hours > hours_max` |
| Language | `language_hard` and any required language's CEFR > `language_max_cefr` and user lacks it |
| Contract type | `contract_type_hard` and `contract_type` ∉ `contract_types` |
| Job type | `job_analysis.contract_type` maps outside `settings.job_types` |
| Recency | `posted_at` older than `recency_days` (when date known) |
| Blacklist | any `keywords_block` term appears in title or must‑haves |
| Eligibility | module on and (enrollment impossible for the period, or non‑EU day budget already exhausted) |

**Build — `pipeline/score.py` (soft score 0–100):** each component returns 0..1; contribution =
`component * weight`; `soft_score = 100 * Σcontrib / Σweights`.

| Component | Computation | Default weight |
|---|---|---|
| `skills_match` | over `job_analysis.skills`: required skills matched (exact or embedding ≥ 0.6 against profile skills) weighted ×2 vs nice‑to‑have; = matched_weight / total_weight | 30 |
| `field_relevance` | cosine(`embed(title + summary)`, `embed(join(target_titles + target_fields))`) rescaled from [0.3,0.9]→[0,1] | 20 |
| `language_fit` | 1 if all required languages ≤ user level; 0.5 if one level above and constraint soft; 0.15 if far above | 15 |
| `hours_fit` | 1 if `weekly_hours ≤ hours_max`; else linear decay to 0 at `hours_max + 15` (only reached when soft) | 10 |
| `seniority_fit` | 1 for student/entry/junior; 0.5 mid; 0.2 unknown‑but‑senior signals | 8 |
| `recency` | 1 at 0 days → 0 at `recency_days` (linear); 0.7 if date unknown | 7 |
| `salary_fit` | if present: 1 when ≥ target rate, linear below; if absent: `0.6` neutral | 5 |
| `company_affinity` | 1 if `company.is_favorite`; 0.8 if in curated registry; 0.5 otherwise | 5 |

- Weights come from `settings.weights_json` (the table above is the seeded default); the UI
  exposes sliders that must re‑normalize visibly.
- `soft_breakdown_json` records `{component: {raw, weight, contribution}}` for the UI chart.

**Tests:** table‑driven — craft `job_analysis` + `settings` combos and assert exact
`hard_failures` and `soft_score` (± rounding). This is the most test‑heavy module.

**Acceptance:** flip `hours_hard` on/off for the same full‑time job → disqualified vs scored‑lower;
breakdown sums to `soft_score`.

---

### CP11 — Judge, blend, decision, documents checklist — *2 sessions*

**Goal:** final verdict per job.

**Build**
- `llm/judge.py` + `prompts/judge.md`. Model: Sonnet. Input: profile summary, `job_analysis`,
  `soft_breakdown`. Output:
  ```json
  {
    "holistic_fit": 0-100,
    "rationale": "2-4 sentences",
    "missing_qualifications": ["..."],
    "strengths_to_highlight": ["..."],
    "recommendation": "apply|maybe|skip"
  }
  ```
  Only run for jobs with `hard_pass=true` **and** `soft_score ≥ threshold_maybe − 10` (don't
  spend Sonnet on clear rejects).
- `final_score = round(blend_soft_ratio * soft_score + (1 − blend_soft_ratio) * holistic_fit)`.
  Jobs that skipped the judge use `final_score = soft_score`.
- Decision buckets from `settings` thresholds → `recommended | maybe | archived`.
- `pipeline/documents.py`: build `documents_needed` from `job_analysis.documents_requested`,
  `application_method`, `contract_type`, `enrollment_required`:
  - CV → always `required`.
  - Cover letter → `required` if requested, else `optional`.
  - Immatrikulationsbescheinigung → `likely` for Werkstudent / when enrollment mentioned, else
    `optional`.
  - Transcript → `required`/`likely` if grades/Notenspiegel requested.
  - Reference letters, portfolio/GitHub → per `documents_requested`.
  Each entry carries a `reason` (quote the snippet where possible) and whether you currently
  have that document uploaded.

**Acceptance:** end‑to‑end on 20 real jobs → sensible buckets; a job that asks for a transcript
shows Transcript = required with the quote.

---

### CP12 — Pipeline orchestrator — *2 sessions*

**Goal:** one function runs the whole thing, resumably.

**Build**
- `pipeline/orchestrator.py::run(trigger)` implementing §1.2, each stage in its own try/except
  writing to `run.errors_json`; stage timings logged.
- Idempotent: safe to run twice a day; only new/changed jobs cost tokens.
- Budget guard (see CP14) checked before each LLM batch.
- `POST /api/runs` → start a manual run (returns `run_id`, streams progress via SSE
  `GET /api/runs/{id}/events`); `GET /api/runs`, `GET /api/runs/{id}`.
- CLI: `just run-pipeline` with flags `--fetch-only`, `--no-llm`, `--source=ba`, `--limit=20`.

**Acceptance:** manual run from the UI shows live stage progress and a final stats summary;
killing one source's network still completes the run.

---

### CP13 — Scheduler — *1 session*

**Goal:** it runs itself every morning.

**Build**
- `scheduler.py`: APScheduler `CronTrigger` from `settings.run_time` + `run_timezone`;
  re‑registered whenever settings change; a missed run (laptop asleep) fires on next wake via
  `misfire_grace_time` + `coalesce=True`.
- `deploy/com.findmyjob.daily.plist`: a `launchd` `StartCalendarInterval` job that calls
  `just run-pipeline` — belt‑and‑braces so a run happens even if the server process is down;
  the orchestrator's idempotency makes a double‑run harmless.
- `deploy/com.findmyjob.server.plist` (optional): keep the FastAPI server always up with
  `KeepAlive`.
- README section: `launchctl load` instructions, how to change the time.

**Acceptance:** set `run_time` 2 minutes out → a run appears; `launchd` job triggers a run with
the server stopped.

---

### CP14 — Cost controls — *1 session*

**Goal:** predictable spend.

**Build**
- `services/cost.py`: current‑month token totals from `llm_call_log`; `remaining_budget()`;
  price table per model (input/output €/Mtok) in config.
- `llm/client.py`: every call goes through here — model routing by `purpose`, token accounting,
  a content‑hash response cache table, `cache_hit` logging.
- Orchestrator: before each LLM stage, if `remaining_budget()` would go negative, set
  `run.budget_exhausted=true`, stop analyzing, leave the rest for tomorrow, note it in the
  digest.
- Pre‑filter ordering guarantees no LLM call for hard‑failed jobs.
- `GET /api/costs` → month‑to‑date €, per‑purpose breakdown, projection.

**Acceptance:** set budget very low → run analyzes a few jobs then stops cleanly; `GET /api/costs`
matches `llm_call_log` sums.

---

### CP15 — Frontend scaffold, auth, API client — *1 session*

**Build**
- First‑run screen: set passphrase → `app_auth` row; thereafter a login screen; signed cookie
  session; all `/api/*` except `/health` require it.
- `api/client.ts` (fetch wrapper, error toast) + TanStack Query hooks per resource.
- App shell: sidebar nav (Dashboard, Tracker, Runs, Settings), route guards.

**Acceptance:** cold start → set passphrase → land on empty Dashboard; logout/login works.

---

### CP16 — Onboarding wizard UI — *2 sessions*

**Goal:** the "set it up once" flow.

**Build** a stepper:
1. **Documents** — upload CV (required) + others; trigger parse; show progress.
2. **Profile review** — the CP3 screen; confirm/edit.
3. **Where & what** — city, radius, remote toggle, `target_fields`, `target_titles`, `job_types`.
4. **Keywords** — run suggestion; drag chips into Allow / Block / Ignore.
5. **Limits** — hours (+ hard toggle), language max CEFR (+ hard), contract types (+ hard),
   recency window, score threshold, weight sliders (advanced, collapsible).
6. **Schedule & alerts** — run time, timezone, notification channel(s) + destination, monthly
   budget, cover‑letter language mode + tone.
7. **Eligibility (optional)** — nationality/EU status; if non‑EU, enable the day tracker and
   enter semester lecture dates.
8. **Review & finish** — summary; "Run first search now" button.

Re‑entrant: every step is also reachable from Settings later.

**Acceptance:** a new user completes onboarding and a first run produces recommendations.

---

### CP17 — Dashboard UI — *2 sessions*

**Build**
- Recommended jobs as cards, **descending by `final_score`**, score as a ring/badge.
- "New since last run" badge + a filter toggle (`first_seen_run_id == latest`).
- Filters: bucket (recommended / maybe / all), source, company, job type, has‑salary,
  posted‑within, search.
- Secondary "Maybe" section (collapsed).
- Each card: title, company, location, hours, salary if known, top‑2 strengths, top missing
  qualification, age, source.
- Empty/failed‑run states; link to the run that produced the list.

**Acceptance:** with ~50 scored jobs the list sorts and filters correctly; new‑run badge is
accurate.

---

### CP18 — Job detail UI — *2 sessions*

**Build**
- Header: title, company (link to careers), location, posted date, source, **Apply** button
  (opens `apply_url`/`url` in a new tab).
- **Match breakdown**: Recharts bar of component contributions; hard‑filter status; judge
  rationale; missing qualifications; strengths to highlight.
- **Analysis**: must‑haves / nice‑to‑haves, skills (matched vs not, visually), languages, hours,
  salary, start date, deadline, application method, red flags — each with a hover showing the
  source snippet.
- **Documents checklist**: each doc with necessity, reason (quoted), and ✓/✗ have‑it.
- **Original description**: rendered `jd_text` (sanitized) with a link to the source.
- **Status control**: set application status; set a follow‑up date.
- **Prepare cover letter** button (enabled always; see CP19).

**Acceptance:** every number on the page traces to data; snippets appear on hover; status change
persists and reflects on the Tracker.

---

### CP19 — Cover letter generation & DOCX — *3 sessions*

**Goal:** the payoff feature.

**Build**
- `docx/template.docx`: DIN 5008 Form B letter — your address block, date (right), recipient
  block, bold subject line, salutation, body, closing, name. Jinja fields via `docxtpl`:
  `{{ sender.* }}`, `{{ recipient.* }}`, `{{ date }}`, `{{ subject }}`, `{{ salutation }}`,
  `{% for p in paragraphs %}`, `{{ closing }}`.
- `llm/cover_letter.py` + `prompts/cover_letter.md`. Model: Sonnet. Inputs:
  - structured profile + `profile_skill` + `highlights_from_references`,
  - `job_analysis` + `jd_text` (for company/role specifics — **only** facts present in the
    posting, to curb hallucination),
  - `strengths_to_highlight` from the judge,
  - `voice_sample_text` as a style few‑shot,
  - `cover_letter_language_mode` → resolve target language (detect posting language when
    `match_posting`),
  - `cover_letter_tone`.
  Output JSON:
  ```json
  {
    "language": "de",
    "recipient": {"company": "", "name": null, "street": null, "postal_code": null, "city": null},
    "subject": "Bewerbung als Werkstudent ... – <your name>",
    "salutation": "Sehr geehrte Damen und Herren,",
    "paragraphs": ["hook / why this company (1 concrete, posting-specific sentence)",
                   "fit: 2-3 claims, each backed by profile evidence",
                   "logistics: enrollment, hours available, start date",
                   "close: availability for interview"],
    "closing": "Mit freundlichen Grüßen",
    "claims_used": [{"claim": "...", "evidence_from_profile": "..."}]
  }
  ```
  Prompt rules: target ~250–330 words; ban a buzzword list (`synergy`, `passionate about`,
  `dynamic team player`, `hit the ground running`, …); require one posting‑specific concrete
  detail; no invented metrics/employers; if recipient name/address unknown, use the generic
  salutation.
- `docx/render.py`: fill the template → save `letters/<job_id>/Cover letter <Company> v<n>.docx`.
- Endpoints: `POST /api/jobs/{id}/cover-letter` (generate → returns `content_json` + `claims_used`),
  `PUT /api/cover-letters/{id}` (save user edits — sets `user_edited=true`, re‑renders DOCX),
  `POST /api/cover-letters/{id}/regenerate` (with optional instruction),
  `GET /api/cover-letters/{id}/docx` (download).
- Frontend: an editor page — left = editable fields/paragraphs, right = `claims_used` table (so
  you verify every claim), buttons: Regenerate, Regenerate with instruction, Save, Download.
  On generate, if a required doc is missing, a banner reminds you.
- Creating a cover letter auto‑advances the `application` status to `preparing` (if lower).

**Acceptance:** for a real posting, generate → every claim maps to real profile evidence →
edit one paragraph → download → the `.docx` opens in Word/Pages with correct DIN 5008 layout and
your edits.

---

### CP20 — Application tracker — *1–2 sessions*

**Build**
- Board view by `application.status` (interested / preparing / applied / interview / offer /
  rejected / withdrawn); drag between columns; each card links to the job + its cover letter.
- Set `applied_at`, `documents_used`, `follow_up_at`, `outcome_note`.
- A "Follow‑ups due" list (where `follow_up_at ≤ today` and status = applied); surfaced on the
  Dashboard and in the digest.
- `GET/POST/PUT /api/applications`.

**Acceptance:** move a job to "applied" with a date → it appears under follow‑ups after the set
interval; counts on the Dashboard update.

---

### CP21 — Notifications (digest) — *1 session*

**Build**
- `services/notifications.py`: channels `email` (SMTP creds in `.env`) and `telegram` (bot token
  in `.env`, chat id in settings). Interface `send(subject, body_markdown, body_html)`.
- After each run: compose a digest — run stats, top `N` (default 8) **new** recommendations
  (title, company, score, one‑line why, deep link `http://127.0.0.1:8000/jobs/<id>`), any
  follow‑ups due, budget/error warnings.
- `POST /api/notifications/test`.

**Acceptance:** a completed run delivers the digest on the configured channel with working deep
links.

---

### CP22 — Eligibility module (optional) — *2 sessions*

**Goal:** encode Werkstudent constraints and the non‑EU working‑day limit. Behind
`settings.eligibility_module_enabled`.

**Build**
- `services/eligibility.py`:
  - **20h rule:** during a lecture period (`semester_calendar`), flag jobs whose
    `weekly_hours > 20` as a soft/hard eligibility issue (configurable); outside lecture periods,
    allow more.
  - **Enrollment horizon:** if `enrollment_valid_until` or `expected_graduation` is before the
    job's likely start + a minimum tenure, flag it.
  - **Non‑EU 140/280 days:** `eligibility_ledger` accrues worked days from applications marked
    `applied`→`offer`→accepted (user confirms actual start/end + full/half day). A gauge shows
    days used vs the annual limit; when projected to exceed, new full‑time‑ish jobs get an
    eligibility hard‑fail (if configured) or a heavy penalty.
- Hooks into CP10 pre‑filter (`hard_failures += ["eligibility:…"]`) and CP17/CP18 (a badge).
- UI: an Eligibility page — the gauge, the ledger (add/edit periods), semester dates editor, a
  plain‑language explanation with a disclaimer that this is guidance, not legal advice, and the
  authoritative source is the Ausländerbehörde / your enrollment office.

**Acceptance:** with the module on and a near‑exhausted ledger, a 30h/week role during term is
flagged with a clear reason; turning the module off removes all such flags.

---

### CP23 — Observability, retention, backup — *1 session*

**Build**
- `GET /api/runs/{id}` detail page in the UI: per‑stage timings, per‑source counts, errors,
  tokens, €.
- Structured logs rotated (`RotatingFileHandler`, 10×5 MB).
- Retention job (runs weekly): delete `archived` jobs + analyses older than
  `retention_days` (default 90); keep anything linked to an `application` or `cover_letter`
  forever.
- Backup: nightly `sqlite3 .backup` to `data/backups/findmyjob-YYYYMMDD.db` (keep 14);
  documents/letters are already plain files.

**Acceptance:** run detail page renders; retention prunes a seeded old archived job but keeps one
tied to an application; a backup file appears.

---

### CP24 — Packaging & macOS deployment — *1 session*

**Build**
- `just setup` — creates venv, installs backend + frontend deps, builds the frontend into
  `backend/app/static`, runs migrations + seed, downloads the MiniLM model.
- `just start` — runs Uvicorn serving API + built UI on `127.0.0.1:8000`.
- Install the two `launchd` plists (`just install-launchd` / `uninstall-launchd`).
- README: prerequisites (Python 3.12, Node 20), `.env` walkthrough (which API keys, where to get
  each), first‑run, changing the schedule, where data lives, how to back up, how to reset.
- A `just doctor` command: checks Python/Node versions, `.env` completeness, DB reachable, each
  configured source authenticates, Anthropic key valid, MiniLM present.

**Acceptance:** on a clean machine, `just setup && just start` → onboarding works end to end;
`just doctor` all‑green.

---

### CP25 — Calibration & feedback loop (v2) — *2 sessions*

**Goal:** the scores get better over time.

**Build**
- On job cards / detail: 👍 / 👎 "was this a good recommendation?" → `job_feedback` table
  (`job_id, verdict, note`).
- Outcome signal: `application.status` transitions (applied, interview, offer) are positive
  labels; `withdrawn`/`rejected`‑without‑interview are weak negatives.
- A `just calibrate` report: correlation of each soft component (and the judge score) with
  positive outcomes; suggested weight adjustments; the user applies them with one click (writes
  `settings.weights_json`).
- Optional: a per‑user logistic‑regression re‑ranker over the component vector once there are
  ≥ 40 labeled jobs, blended with the rule score behind a feature flag.

**Acceptance:** after labeling a sample, the report shows per‑component correlations and a
proposed weight set; applying it changes future rankings.

---

## 6. Milestones (checkpoint groupings)

| Milestone | Checkpoints | Outcome |
|---|---|---|
| **M1 — Foundation** | CP0–CP4 | App runs; documents parsed into a profile; all preferences persisted |
| **M2 — Ingestion** | CP5–CP8 | Daily fetch from all allowlisted sources, enriched and deduplicated, in the DB |
| **M3 — Intelligence** | CP9–CP12 | Every job analyzed, scored, judged, bucketed, with a documents checklist; one‑command pipeline |
| **M4 — Automation** | CP13–CP14 | Runs itself every morning within a fixed budget |
| **M5 — Product** | CP15–CP20 | Full web UI: onboarding, dashboard, job detail, cover letters, tracker |
| **M6 — Polish** | CP21–CP24 | Digest notifications, eligibility module, observability, packaged for macOS |
| **M7 — Learning** | CP25 | Feedback‑driven score calibration |

**Usable at M5** (with the pipeline run manually if M4 slips). **M1–M3** is the critical path.

---

## Appendix A — Config & secrets

`.env` (secrets only):

```
FINDMYJOB_DATA_DIR=            # optional override
FINDMYJOB_SECRET_KEY=          # cookie signing
ANTHROPIC_API_KEY=
BA_API_CLIENT_ID=              # Bundesagentur für Arbeit
BA_API_CLIENT_SECRET=
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
THEMUSE_API_KEY=
SMTP_HOST= SMTP_PORT= SMTP_USER= SMTP_PASS= SMTP_FROM=
TELEGRAM_BOT_TOKEN=
```

Everything else (city, radius, weights, thresholds, schedule, channels, budget, enabled sources,
eligibility) lives in the `settings` table and is edited in the UI.

Model price table (config, €/Mtok, edit to match current pricing):

```
claude-haiku   : {input: ..., output: ...}
claude-sonnet  : {input: ..., output: ...}
```

---

## Appendix B — LLM prompt contracts

Each prompt file lives in `backend/app/llm/prompts/` and is versioned.

| Prompt | Model | Purpose | Output |
|---|---|---|---|
| `profile_parser.md` | Haiku | CV + docs → structured profile | JSON (CP3) — every field, plus `evidence` quotes |
| `keyword_suggest.md` | Haiku | fields + skills → keyword candidates | `{core[], adjacent[], tools[], likely_noise[]}` |
| `analyzer.md` | Haiku | posting → structured facts | `job_analysis` JSON + `source_snippets` |
| `judge.md` | Sonnet | profile + analysis + soft breakdown → holistic fit | `{holistic_fit, rationale, missing_qualifications[], strengths_to_highlight[], recommendation}` |
| `cover_letter.md` | Sonnet | profile + posting + strengths + voice sample → letter | JSON (CP19) + `claims_used[]` |

Shared rules for all prompts: return **only** JSON; never invent facts not in the inputs; when
unsure use `null`/`"unknown"`; quote source text for every extracted constraint.

---

## Appendix C — Scoring defaults (seed values)

```
weights = { skills_match:30, field_relevance:20, language_fit:15, hours_fit:10,
            seniority_fit:8, recency:7, salary_fit:5, company_affinity:5 }
blend_soft_ratio = 0.6           # final = 0.6*soft + 0.4*judge
score_threshold_recommend = 70
score_threshold_maybe = 55
semantic_dupe_threshold = 0.92
skill_match_embedding_threshold = 0.6
repost_days = 21
retention_days = 90
```

---

## Appendix D — Werkstudent reference notes (for the eligibility module)

Guidance only — not legal advice. The app must display this caveat and point to the
Ausländerbehörde / enrollment office as authoritative.

- **Working‑student status ("Werkstudentenprivileg"):** typically ≤ 20 h/week during the lecture
  period; more is allowed during semester breaks. Exempt from health/care/unemployment insurance
  contributions (pension contribution still applies). Requires active full‑time enrolment;
  usually not available in the final/exmatriculation semester.
- **Non‑EU/EEA students:** may work **140 full days or 280 half days per calendar year** without
  additional permission; working‑student employment counts toward this. Exceeding it needs
  Ausländerbehörde approval. The ledger in CP22 tracks cumulative days from confirmed
  employment.
- **Semester dates** vary by university and are entered manually in `semester_calendar`.

---

## Appendix E — Testing strategy

| Layer | Approach |
|---|---|
| Source connectors | `respx`‑mocked HTTP with recorded real responses; assert `RawJob` mapping, filtering, job‑type translation |
| Normalization / dedup | fixture sets: identical cross‑source, paraphrased, distinct; assert linking |
| Scoring | table‑driven unit tests over `(job_analysis, settings) → (hard_failures, soft_score)` |
| LLM modules | schema‑validate outputs against Pydantic; snapshot‑test structure (not wording) with `syrupy`; a small "golden set" of ~15 real postings reviewed manually per analyzer version |
| Pipeline | integration test with all sources mocked + a stub LLM client → asserts `Run` stats and DB state |
| API | FastAPI `TestClient` per route, auth‑gated |
| Frontend | Vitest + React Testing Library for the wizard, dashboard sorting/filtering, cover‑letter editor |
| Cost guard | budget set to near‑zero → asserts partial run + `budget_exhausted` |

---

## Appendix F — Risks & mitigations

| Risk | Mitigation |
|---|---|
| A source changes its API / goes away | Connectors isolated; run tolerates per‑source failure; `just doctor` flags auth breakage early |
| LLM extracts wrong facts | JSON‑schema validation + repair retry; `source_snippets` provenance shown in UI; you review before applying |
| Cover letter reads as AI‑written | Banned‑phrase list, word‑count cap, your voice sample as few‑shot, mandatory human edit step, `claims_used` review table |
| Score doesn't match your judgment | Visible breakdown, tunable weights, CP25 calibration loop |
| Token cost creeps | Pre‑filter before LLM, content‑hash cache, monthly budget hard stop, Haiku for bulk work |
| Duplicate or expired postings | 3‑tier dedup, `lifecycle=dead` on 404, repost window |
| Laptop asleep at run time | APScheduler misfire grace + coalesce; independent `launchd` trigger; idempotent pipeline |
| Personal data in documents | All local, `127.0.0.1` only, passphrase gate, retention pruning, nothing sent anywhere except the LLM calls you configure |
| Missing salary/date fields (common in DE) | Neutral scoring for absent data, never a hard fail on unknowns |

---

## Appendix G — Future enhancements (post‑v1)

- Paid aggregator connector (official Google Jobs reseller API) behind the same interface for
  wider coverage.
- Browser extension: "analyze this posting" button on any career page → pushes into the pipeline.
- Interview prep: generate likely questions per posting from the analysis + your gaps.
- Multi‑city / multiple saved search profiles.
- iCal feed of application deadlines and follow‑ups.
- LLM‑drafted follow‑up emails after N days of silence.
- Auto‑attach the right documents into a per‑application zip.
