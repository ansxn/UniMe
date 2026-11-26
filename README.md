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

## Accounts (optional, Supabase)

Accounts let students save their results. They never gate anything: guests can still take the quiz and use ChanceMe.

- **Sign up, log in, log out, and forgot/reset password** use email and password through Supabase Auth, and Supabase sends the emails. The pages are `/login` (log in, sign up, or forgot password, chosen by `?mode=`), `/reset-password` (where the reset email lands), and `/account`.
- **What gets saved:** each quiz attempt (answers, the `/api/match` response, and a timestamp), each ChanceMe check that finds the program (inputs and `prediction`), and programs starred on `/matches`. `/account` lists all three with delete buttons, and clicking a quiz result reopens it in `/matches`. It also has the profile (display name, optional grad year) and log out.
- **Guest flow:** after results show, a "Save your results" prompt appears. Whatever the guest asked to save is queued in localStorage (`unime:pending`). After they sign up or log in, it is saved automatically and they return to the page they came from. For logged-in users, quiz attempts and ChanceMe checks are saved automatically.
- **Code:** `src/lib/supabase.ts` (the single browser client), `src/lib/saved.ts` (data access and pending saves), `src/components/AuthProvider.tsx` and `AuthPill.tsx` (session context and the top-right pill), and `src/app/accounts.css`.

**Setup**

1. Apply `supabase/migrations/20261125000000_accounts.sql`, either with `supabase db push` or by pasting it into the SQL editor. It creates `profiles` (filled by a signup trigger), `quiz_results`, `chance_checks`, and `saved_programs`, all with row-level security that limits each user to their own rows.
2. Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (or the legacy `NEXT_PUBLIC_SUPABASE_ANON_KEY`) in `frontend/.env.local` and in the Vercel project. See `frontend/.env.example`. Both values are public. **If they're unset, accounts are off:** the auth UI is hidden and the app works exactly as it does without accounts.
3. In Supabase, open Auth → URL Configuration. Set the Site URL to the production domain and add redirect URLs for `http://localhost:3000/**`, the production domain `/**`, and Vercel preview URLs if wanted. Sign-up confirmation and password-reset links come back to these URLs.

## Data notes

- `program_profiles.json`: 1,399 program profiles. About 150 have no campus data and get a neutral campus score.
- `admissionsData.csv`: about 2,000 crowd-sourced results. Many programs have only a handful of offers, and the UI flags estimates built on fewer than 5.
- To add a mentor, add an entry to `data/mentors.json`, put the photo in `public/mentors/`, and map `"<uni>_<program>"` (exactly as written in `program_profiles.json`) to the mentor's id under `programMentors`.
