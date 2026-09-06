# User guide

How to install and use FindMyJob. This tracks what actually works today; parts
marked _(coming in CPn)_ are not built yet.

## What it does

Every morning it searches allowlisted job boards and company career pages for
working-student ("Werkstudent") and related student roles in your city,
analyzes each posting, scores how well it fits your CV and preferences, and
shows you the good ones — highest match first. When you find one worth applying
to, one click drafts a tailored cover letter you download as a `.docx`, polish,
and submit yourself. It never applies for you and never scrapes sites that
forbid it.

## Install

```bash
cd FindMyJob
cp .env.example .env
```

Edit `.env` and set at least:

- `ANTHROPIC_API_KEY` — for analysis and cover letters
- optionally `BA_API_CLIENT_ID` / `BA_API_CLIENT_SECRET` (Bundesagentur für
  Arbeit), `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`, `THEMUSE_API_KEY` — more job
  sources. Arbeitnow and company ATS endpoints need no key.

Then:

```bash
python3 -m venv .venv
just setup          # installs deps, runs migrations, seeds defaults
just doctor         # verify everything is wired
just dev            # starts the app on http://127.0.0.1:8000
```

No `just`? See the commands in the top-level `README.md`.

## First-time setup

Open `http://127.0.0.1:8000`, set a passphrase, and the onboarding wizard walks
you through it:

1. **Upload documents** — CV (required), plus optionally enrollment
   certificate, transcript and reference letters.
2. **Parse your CV** — the wizard reads your documents and fills in a structured
   profile (name, university, enrollment dates, skills, languages).
3. **Review the profile** — correct anything; fields you edit are "locked" and a
   later re-parse won't overwrite them. Set the voice sample to a cover letter
   you wrote yourself — it makes generated letters sound like you.
4. **Set preferences** — city, radius, target fields and job titles (with LLM
   keyword suggestions), keyword allow/block lists, weekly-hours limit (and
   whether it's a hard limit), language level, score thresholds and weights,
   daily run time, sources, and the optional eligibility module.

Everything is saved between sessions and re-editable later from **Settings**.

### Running the LLM steps

Three ways, in `.env`:

**1. Offline stub — no key, no network, zero cost.**
`LLM_OFFLINE=true`. CV parsing, keyword suggestions, analysis, judge and
cover-letter generation return canned, schema-valid placeholder data. Proves the
plumbing (scoring, buckets, DOCX export, tracker) end to end; the text is fake.

**2. A free / non-Anthropic model — real output, no Anthropic bill.**
Point the client at any OpenAI-compatible `/chat/completions` endpoint:

```ini
LLM_OFFLINE=false
LLM_PROVIDER=openai
LLM_OPENAI_BASE_URL=https://api.groq.com/openai/v1     # Groq: free, fast, needs a free account
LLM_OPENAI_API_KEY=gsk_...                             # from console.groq.com/keys
LLM_MODEL_CHEAP=llama-3.1-8b-instant
LLM_MODEL_SMART=llama-3.3-70b-versatile
```

Endpoints that work the same way (check each provider's current model list — they
rename models often):

| Provider | `LLM_OPENAI_BASE_URL` | Key | Free-tier fit |
|---|---|---|---|
| **Google Gemini** | `https://generativelanguage.googleapis.com/v1beta/openai` | free, `aistudio.google.com/apikey` | **best** — ~1M tokens/min, comfortably analyses a whole run |
| **Groq** | `https://api.groq.com/openai/v1` | free, `console.groq.com/keys` | tight — most models cap at 8k tokens/min; use a higher-limit one like `groq/compound-mini` and expect the odd pause |
| **Cerebras** | `https://api.cerebras.ai/v1` | free, `cloud.cerebras.ai` | moderate |
| **Ollama (local)** | `http://localhost:11434/v1` | none — `ollama pull <model>` first | unlimited, slower, needs RAM |

A single daily run analyses 40-90 postings at a few thousand tokens each. The
client honours a `429 Retry-After` and pauses, so a tight free tier still
finishes - it just takes longer. Spend is recorded as €0 (billed on the
provider's own quota, if at all). Quality is below Claude on the JSON-extraction
prompts; the client retries once on malformed JSON.

**3. Anthropic (Claude) — best quality.**
`LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=sk-ant-...`, `LLM_OFFLINE=false`.
New accounts get trial credit; a full run costs a few cents (Haiku for bulk,
content-hash cache, `LLM_MONTHLY_BUDGET_EUR` hard stop).

## Daily use

- Open the dashboard each morning. New recommendations are badged; the
  **Activity** tab shows a digest per run.
- Click a job to see the match breakdown ("why this score"), the extracted
  requirements, the original description, the apply link, and which of your
  documents it needs.
- Give the recommendation a 👍 or 👎 in the drawer. That, plus how far you take
  each application in the tracker, feeds the calibration panel.
- If you like it after reading it yourself, click **Prepare cover letter**.
  Review the draft (every claim is traced back to something in your profile),
  edit inline, then **Download** `Cover letter <Company>.docx`.
- Track status per job: interested → applied → interview → outcome.

## Tuning the score

Once you have rated about eight jobs (👍/👎 or advanced in the tracker), open
**Settings → Score calibration**. It shows how strongly each score component
correlated with the jobs you liked and proposes an adjusted weight set. Click
**Apply suggested weights** to use them for future rankings, or run
`just calibrate` / `just calibrate --apply` from the terminal. Nothing changes
until you apply it, and you can always re-edit the weights by hand in Settings.

## Running the pipeline manually

```bash
just run-pipeline                         # run the whole daily job now
just run-pipeline --fetch-only            # only ingest postings
just run-pipeline --source ba --limit 20  # one source, capped (debugging)
findmyjob pipeline list                   # show the configured stages
findmyjob calibrate                       # suggested score weights from feedback
```

Inspect past runs from the **Runs** tab in the web UI (per-stage status,
timing, LLM usage, errors).

## Where your data lives

Everything is local, under `data/` (git-ignored):

- `findmyjob.db` — the database
- `documents/` — your uploaded files
- `letters/` — generated cover letters
- `logs/findmyjob.log` — structured logs

The only outbound network calls are to the job-source APIs you enable and to
the Anthropic API. Nothing is shared or uploaded anywhere else.

## Privacy & safety

- Binds to `127.0.0.1` only.
- A passphrase gate protects the UI _(CP15)_.
- No automated application submission — you always submit yourself.
- Sources are allowlisted: no LinkedIn / StepStone / Indeed scraping.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'findmyjob'` (macOS) | `just fix-venv` — Python 3.13 skips `.pth` files if `.venv` has the macOS _hidden_ flag; this clears it. |
| Dashboard empty after a run | every job was hard-filtered or bucketed as _archived_ — loosen thresholds / hours / recency in **Settings**, or check the run's errors on the **Runs** tab. |
| `LLM ... call failed` / malformed JSON | free models sometimes return bad JSON; the repair retry usually covers it. Persistent failures: try the other model tier or a different provider. |
| `models fetch` fails | offline, or Hugging Face rate-limited - dedup's semantic tier just skips; retry later. |
| Port 8000 in use | set `APP_PORT=8001` in `.env`. |
| Editor flags `tsconfig.json` | cosmetic; reload the window. |
