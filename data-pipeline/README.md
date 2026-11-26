# UniMe data pipeline

Rebuilds the two data files the API reads:

| Output (in `frontend/api/_unime/data/`) | Built by | Used by |
|---|---|---|
| `program_profiles.json` | `build_programs.py` | MatchMe (`scoring.py`), ChanceMe official-range fallback (`chance.py`) |
| `admissionsData.csv` | `build_admissions.py` | ChanceMe (`chance.py`) |

This folder lives at the repo root, outside `frontend/`, so none of it is bundled into the Vercel function. It uses only the Python standard library (3.10+). It needs no `pip install`, no API keys, and no LLM or paid APIs.

## Re-running

```bash
cd data-pipeline
python run_all.py              # uses cache/ for anything already downloaded
python run_all.py --refresh    # re-download the Google Sheets
python run_all.py --skip-probe # don't contact OUInfo at all
python -m pytest tests -q      # offline pipeline tests (needs pytest)
cd ../frontend && python -m pytest tests -q   # API tests against the new data
```

`build_programs.py` has to run before `build_admissions.py`, because admissions rows are matched to profile program names. `run_all.py` runs them in that order.

### Layout

```
data-pipeline/
  run_all.py            # runs both builders in order
  build_programs.py     # program catalogue + facts + trait provenance
  build_admissions.py   # multi-cycle crowd-sourced admissions
  fetch.py              # polite cached HTTP (robots.txt, >=1.5 s throttle, generic UA)
  sources.py            # source registry (sheet IDs, OUInfo base URL)
  universities.json     # curated per-university table (city, campus, social)
  baseline/             # the June 2025 inputs UniMe shipped with (frozen)
  manual/               # optional hand-supplied inputs (see below)
  cache/                # raw downloads, gitignored
  tests/                # offline tests
```

School names are canonicalized by `frontend/api/_unime/schools.py`. The API and the pipeline share that file, so admissions rows and program profiles always use the same names, such as `University of Waterloo` and `Toronto Metropolitan University`.

## Sources (retrieved 2026-11-25, America/Toronto)

### Admissions: crowd-sourced r/OntarioGrade12s results sheets

These are public Google Form response sheets, one per application cycle. `year` is the fall the applicants start university.

| Cycle | year | Sheet | Status on 2026-11-25 | Rows used |
|---|---|---|---|---|
| 2022-2023 | 2023 | [18xQRBO1…e_3o](https://docs.google.com/spreadsheets/d/18xQRBO1X2llysir9GwHPhdRPeJGL-osKhOX7WC4e_3o/edit#gid=1176989226) | Public CSV export OK | 789 |
| 2023-2024 | 2024 | [1X5oygD0…iq2Y](https://docs.google.com/spreadsheets/d/1X5oygD0Mu8v899bRBvklzB-t6saHMS7mrqfH_xsiq2Y/edit#gid=1574433327) | Public CSV export OK | 1,214 |
| 2024-2025 | 2025 | [1j48oJsj…zpjrw](https://docs.google.com/spreadsheets/d/1j48oJsjcAqS9K2wQ-x-W27gYr5LuOT-a96dt_ZZpjrw/edit) | View-only, owner disabled downloads (`downloadable:false`, export returns 401) | 1,883, from `baseline/admissions_2024-2025_legacy.csv` |
| 2025-2026 | 2026 | [1NCN-1lw…5I9A](https://docs.google.com/spreadsheets/d/1NCN-1lw39N9lRyB9bJPfrkJy8v3V-yjnnZ1HjrG5I9A/edit) | View-only, owner disabled downloads | 0 (not available) |

- The sheet IDs were found in public GitHub projects that track the same sheets. Reddit itself was not crawled because its robots.txt disallows all bots. docs.google.com's robots.txt allows `/spreadsheet*` with `Crawl-delay: 1`.
- For the two view-only sheets, the owners turned off downloading. The pipeline respects that: it does not scrape the HTML grid and does not use other endpoints. If you get a CSV export from the owner, save it as `manual/2024-2025.csv` or `manual/2025-2026.csv`. A file in `manual/` takes precedence over the download and the baseline. The reader matches columns by header text, so the raw form layout works as is.
- `baseline/admissions_2024-2025_legacy.csv` is the `admissionsData.csv` UniMe shipped with, committed 2025-06-22. Its columns match the 2024-2025 form, and the date fits the end of that cycle, so it is labelled 2024-2025. Its second line says some rows were "imported from the other spreadsheet". Cross-cycle overlap on (school, program, average) is in line with chance (153 shared keys with 2023-24 vs 94 with 2022-23), so those rows were not removed.

### Programs: OUInfo (ontariouniversitiesinfo.ca → ouinfo.ca)

Checked 2026-11-25. **Not scraped.**

- `ouinfo.ca/robots.txt` disallows `ClaudeBot` and `anthropic-ai` (among other AI crawlers).
- Every page, including `robots.txt` and `/sitemap_index.xml` for non-browser clients, returns a Cloudflare "Just a moment..." bot challenge (HTTP 403).

OUAC (ouac.on.ca) is behind the same challenge. Getting past either would mean defeating an explicit block, so the pipeline doesn't. `build_programs.py` only probes and logs the status.

What the pipeline does instead:

1. **Catalogue**: the June 2025 profiles (`baseline/program_profiles_2025-06.json`, 1,399 rows) are the base. School names are canonicalized: dash variants are unified, "Toronto Metropolitan University (formerly Ryerson University)" becomes "Toronto Metropolitan University", and zero-width characters are stripped from program names. After de-duplication there are 1,393 programs.
2. **Official facts, by hand (optional)**: put rows in `manual/official_programs.csv`, using the same columns as `manual/official_programs.example.csv`:
   - `uni`
   - `program`
   - `campus`
   - `degree`
   - `coop` (`only` | `available` | `none`)
   - `prerequisites` (`;`-separated, e.g. `ENG4U;MCV4U`)
   - `admission_range` (OUInfo wording such as `Low 90s`, `Mid-to-high 80s`, `80%+` or `85-90%`)
   - `source_url`
   - `retrieved`

   Rows that match an existing program (loose name matching, `schools.best_program_match`) add facts to it. Rows that don't match become new programs with derived traits. The file is absent today, so no program has an `admission_range` yet.
3. **Facts derived from the program title** (deterministic):
   - `coop_available` / `coop_required`: from "(Co-op Only)", "(Regular/Co-op)" and similar. 239 programs are known; the rest are `null`, meaning unknown, not "no".
   - `degree`: from "(BSc)", "Bachelor of …" and similar. 333 programs.
   - `city` and `university_url`: from the university table.

## Output schema additions

Each program in `program_profiles.json` keeps `uni`, `program`, `academic`, `campus` and `social` unchanged, and gains:

```json
"facts": {"admission_range": null | {"text": "Low 90s", "low": 90, "high": 93},
          "campus_name": null, "city": "Waterloo", "coop_available": true, "coop_required": true,
          "degree": "BASc", "prerequisites": null | ["ENG4U", ...], "source_url": null,
          "university_url": "https://uwaterloo.ca"},
"trait_source": {"academic": "carried_over", "campus": "carried_over", "social": "carried_over"},
"source": {"catalogue": "unime-2025-06" | "official", "facts": "program-title" | "official" | null}
```

`trait_source` values:

- `carried_over`: the program existed in the June 2025 file, and its values are kept exactly as they were.
- `university_table:curated` / `university_table:carried_over`: the section was empty and was filled from `universities.json`.
- `derived:similar_program`: a new program. Its academic traits are the per-trait median of programs with the same core name at other schools.
- `derived:heuristic`: a new program with no similar program. Its traits come from keyword rules in `build_programs._HEURISTICS`, on top of neutral 3s.

`admissionsData.csv` keeps the seven columns the API always read (`University, Program name, Decision, Top 6 Average, Supp App?, Notable info from supp app, Comments`) and adds:

- `year` and `cycle`.
- `profile_match`: `1` when `Program name` was mapped onto a `program_profiles.json` program name.
- `source`: `google-sheet`, `manual-export` or `unime-legacy-2025-06`.

Personal fields (timestamps, Reddit/Discord usernames, citizenship, residence) are never written. `@handles` and similar are stripped from notes.

## Cleaning rules (admissions)

- **School**: mapped to a canonical name via `schools.canonical`, which includes aliases like "UofT - SG", "Queens", "TMU" and "Toronto Metropolitan Universit" (the form's 30-character truncation). A "University of Toronto" row is moved to UTM or UTSC when the program text says Mississauga/UTM or Scarborough/UTSC. Unknown schools and joke entries are dropped.
- **Applicants**: rows where the applicant says they live outside Ontario (2023-24 province field) or are a 105 applicant (2022-23 field) are dropped, because ChanceMe models Ontario top-6 averages.
- **Decision**: normalized to `Offer | Rejected | Deferred | Waitlisted`. "Accepted (conditional)" counts as an Offer.
- **Average**: see `parse_average`. These are accepted:
  - plain numbers, `%`, `~` and `ish`
  - grade qualifiers ("95 gr 12 midterm")
  - "Top 6: x"
  - ranges up to 5 points apart, which use the midpoint
  - "low/mid/high 80s", read as 82 / 85 / 88

  These are rejected: IB points, GPAs, CEGEP R-scores, lists of marks, and anything outside 60-100. In 2023-24, if "Acceptance Average" is blank, the Grade 12 midterm average is used.
- **Program**: whitespace and dashes are cleaned, a leading "School - " prefix is removed, and the UofT campus suffix is stripped. The name is then matched to a profile program name where unambiguous (`schools.best_program_match`). Unmatched names are collapsed to their most common spelling per school. Empty, one-letter, piped multi-program, or over-200-character names are dropped.
- **Duplicates**: exact duplicates within a cycle on (school, program, decision, average, notes) are dropped.

## University table (`universities.json`)

There is one entry per canonical university or campus (34). Each entry has:

- `city` and `official_url`: facts
- `campus` {class_size_bin, setting, housing_styles, campus_size}
- `social` {night_scene, sports, clubs, cultural_event_freq}
- `values_source`

`values_source` is one of:

- `carried_over` (29 schools): the modal value of that school's programs in the June 2025 file. Not used today, because those schools have no empty sections.
- `curated` (5 campuses with no data before): estimates written for this refresh, used to fill the 156 empty `campus` and `social` objects.

| Campus | Setting | Size | Class size | Housing | Night scene | Notes |
|---|---|---|---|---|---|---|
| Toronto Metropolitan University | Urban | Large | 60-200 | dorm, suite, off-campus | 5 | Downtown Toronto. TMU Bold: basketball, hockey, soccer, volleyball (no football) |
| Trent University - Durham GTA | Suburban | Small | < 60 | suite, off-campus | 2 | Oshawa satellite campus |
| University of Guelph-Humber | Suburban | Small | < 60 | suite, off-campus | 3 | Humber North campus, Etobicoke |
| Wilfrid Laurier - Brantford | Small-town | Small | < 60 | suite, apartment, off-campus | 2 | Downtown Brantford |
| Wilfrid Laurier - Milton | Suburban | Small | < 60 | off-campus | 2 | New campus with no residence |

These are subjective, like the rest of the campus/social values. Edit `universities.json` and re-run to change them.

## How ChanceMe uses the data

See `frontend/api/_unime/chance.py`:

- Each offer is weighted `0.7 ** (newest_year - year)`, so the newest cycle counts 1.0, the one before 0.7, then 0.49. The weights feed `offer_average` and `effective_sample_size`. `offer_min` and `offer_max` are still the raw extremes.
- When a program has an official `admission_range`:
  - No crowd offers: `basis: "official"`. The range sets the min and max, and its midpoint sets the average.
  - Effective offers below 5: `basis: "blended"`. The crowd figures and the official range are mixed with `alpha = effective_n / 5`.
  - Otherwise: `basis: "crowd"`.
- New prediction fields: `basis`, `effective_sample_size`, `offers_by_year` and `official_range`. Every earlier field is unchanged.
