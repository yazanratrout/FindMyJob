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

## First-time setup _(onboarding wizard: coming in CP16)_

Until the UI lands, use the API (`http://127.0.0.1:8000/api/docs`):

1. **Upload documents** — `POST /api/documents` with `type` = `cv` /
   `enrollment` / `transcript` / `reference` and the file. CV is required.
2. **Parse your CV** — `POST /api/profile/parse`. This reads your documents and
   fills in a structured profile (name, university, enrollment dates, skills,
   languages).
3. **Review the profile** — `GET /api/profile`, correct anything with
   `PUT /api/profile`. Fields you edit are "locked" and a later re-parse won't
   overwrite them. Set `voice_sample_text` to a cover letter you wrote yourself
   — it makes generated letters sound like you.
4. **Set preferences** — `PUT /api/settings`: city, radius, target fields and
   job titles, keyword allow/block lists, weekly-hours limit (and whether it's
   a hard limit), language level, score threshold, run time, notification
   channel. _(keyword suggestions: coming in CP4; full editor: CP16)_

Everything is saved between sessions.

## Daily use _(coming in CP17–CP19)_

- Open the dashboard each morning. New recommendations are badged.
- Click a job to see the match breakdown ("why this score"), the extracted
  requirements, the original description, the apply link, and which of your
  documents it needs.
- If you like it after reading it yourself, click **Prepare cover letter**.
  Review the draft (every claim is traced back to something in your profile),
  edit inline, then **Download** `Cover letter <Company>.docx`.
- Track status per job: interested → applied → interview → outcome.

## Running the pipeline manually

```bash
just run-pipeline            # run the whole daily job now
findmyjob pipeline list      # show the configured stages
findmyjob runs show <id>     # inspect a run  (coming with CP12/CP23)
```

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
