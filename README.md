# UniMe

Your personal digital guidance counselor for Ontario universities.

- **MatchMe**: a short quiz that ranks ~1,400 Ontario university programs against your interests, learning style, and campus/social preferences, and connects you with current-student mentors. You can also download your top 100 as a PDF.
- **ChanceMe**: estimates your admission chances for a program from crowd-sourced past offers (top-6 average + extracurriculars).

## How it's built

Everything is in `frontend/` and deploys as **one Vercel project**:

| Part | Where | What |
|---|---|---|
| Web app | `frontend/src/app/` | Next.js 16 (App Router), React 19 |
| API | `frontend/api/index.py` | Flask, deployed as a Vercel Python function. `next.config.ts` rewrites `/api/*` to it |
| Scoring and data | `frontend/api/_unime/` | `scoring.py` (MatchMe), `chance.py` (ChanceMe), `pdf_report.py`, and `data/` (program profiles, admissions CSV, mentors) |
| Mentor photos | `frontend/public/mentors/` | Served as static files |
| Tests | `frontend/tests/` | pytest tests for the API |

The browser only ever calls same-origin `/api/...` URLs, so you don't need CORS or an API URL environment variable.

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness and data counts |
| POST | `/api/match` | Quiz answers → top 10 matches |
| POST | `/api/report-pdf` | Quiz answers → PDF of top 100 matches |
| GET | `/api/chance-options` | Schools and program names with admissions data |
| POST | `/api/chance-me` | `{school, program, top6, ecs}` → chance estimate |
| GET | `/api/program-mentors?school=&program=` | Mentors for a program (falls back to the same school, then general) |

Bad input returns `400` with `{"success": false, "error": "..."}`.

## Local development

Requirements: Node 20+ and Python 3.12+.

```bash
cd frontend
npm install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest

npm run dev          # Next.js on :3000 + Flask API on :5001 (proxied at /api)
python -m pytest tests -q
```

`npm run dev:web` and `npm run dev:api` run each side on its own.

## Deploying (Vercel)

The Vercel project's **Root Directory must be `frontend`**. Vercel detects Next.js, installs `requirements.txt` for the Python function, and applies `vercel.json`. No environment variables are required. Pushes to `main` deploy to production, and pull requests get preview deployments.

## Data notes

The data is rebuilt by the pipeline in [`data-pipeline/`](data-pipeline/README.md) (`cd data-pipeline && python run_all.py`). That README lists sources, retrieval dates and cleaning rules.

- `program_profiles.json`: 1,393 Ontario programs. Each program has:
  - quiz traits (`academic`, `campus`, `social`)
  - a `facts` object: city, co-op, degree, prerequisites, official admission range, sources
  - `trait_source`, which records whether each section was carried over from the June 2025 profiles or filled or derived by the pipeline

  Every program now has campus data; the 156 that had none are filled from a curated per-university table. OUInfo blocks automated access, so official prerequisites and admission ranges are only present for programs added through `data-pipeline/manual/official_programs.csv`.
- `admissionsData.csv`: about 3,900 crowd-sourced results from the r/OntarioGrade12s sheets for three cycles (2023, 2024, 2025 entry). It has canonical school names and a `year` column. ChanceMe weights recent cycles more, and blends with the official range when a program has few offers. The prediction's `basis` field reports which data was used. The UI still flags estimates built on fewer than 5 offers.
- To add a mentor, add an entry to `data/mentors.json`, put the photo in `public/mentors/`, and map `"<uni>_<program>"` (exactly as written in `program_profiles.json`) to the mentor's id under `programMentors`.
