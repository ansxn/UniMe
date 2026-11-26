"""ChanceMe: estimate admission chances from crowd-sourced past offers.

admissionsData.csv is built by data-pipeline/build_admissions.py and holds
several application cycles (`year` column). Recent cycles count more
(RECENCY_DECAY per year of age). When a program has few crowd-sourced offers
and its profile carries an official admission range (program_profiles.json
facts.admission_range), the estimate falls back to / blends with that range;
the prediction's `basis` says which ("crowd" | "blended" | "official").
"""
import csv
import re

from . import schools

# Lowercased, punctuation-collapsed alias -> canonical school name
# ("university of waterloo", "uwaterloo", "waterloo" -> "University of Waterloo").
SCHOOL_ALIASES = schools.ALIASES

MIN_SCHOOL_ROWS = 3   # schools with fewer offers aren't offered in the dropdown
RECENCY_DECAY = 0.7   # weight of an offer = RECENCY_DECAY ** (newest year - its year)
MIN_CROWD = 5         # effective (recency-weighted) offers needed to rely on crowd data alone
LOW_CONFIDENCE = 5    # raw offers below this are flagged low_confidence (unchanged)

_AVG_RE = re.compile(r"^\s*~?\s*(\d{2,3}(?:\.\d+)?)\s*%?\s*(?:\(top ?6\))?\s*$", re.I)

_key = schools.key


def _parse_avg(raw):
    m = _AVG_RE.match(str(raw or ""))
    if not m:
        return None
    val = float(m.group(1))
    return val if 50 <= val <= 100 else None


def _parse_year(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def load_admissions(path):
    """Return offer rows as dicts with a parsed numeric 'avg' and int 'year' (or None)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if row.get("Decision", "").lower() != "offer":
                continue
            avg = _parse_avg(row.get("Top 6 Average"))
            if avg is None:
                continue
            row["avg"] = avg
            row["year"] = _parse_year(row.get("year"))
            rows.append(row)
    return rows


def _official_index(programs):
    """{school: {program name: admission_range}} for programs that have one."""
    idx = {}
    for p in programs or []:
        facts = p.get("facts") or {}
        rng = facts.get("admission_range")
        if rng and rng.get("low") is not None:
            idx.setdefault(p["uni"], {})[p["program"]] = {**rng, "source_url": facts.get("source_url")}
    return idx


def resolve_school(rows, school, programs=None):
    """Map user input to a school name present in the data, or None."""
    names = {r["University"] for r in rows} | set(_official_index(programs))
    k = _key(school)
    for name in names:
        if _key(name) == k:
            return name
    alias = SCHOOL_ALIASES.get(k) or schools.canonical(school)
    return alias if alias in names else None


def chance_options(rows, programs=None):
    """Schools (with enough data) and the program names seen for each."""
    by_school, counts = {}, {}
    for r in rows:
        by_school.setdefault(r["University"], set()).add(r["Program name"])
        counts[r["University"]] = counts.get(r["University"], 0) + 1
    for school, progs in _official_index(programs).items():
        by_school.setdefault(school, set()).update(progs)
        counts[school] = max(counts.get(school, 0), MIN_SCHOOL_ROWS)
    return [
        {"school": s, "programs": sorted(p)}
        for s, p in sorted(by_school.items())
        if counts.get(s, 0) >= MIN_SCHOOL_ROWS
    ]


def _ec_bonus(user_ecs, notes, max_bonus=3):
    """+1 for 3+ ECs, +0.5 per EC mentioned in past applicants' notes, capped."""
    matches = sum(1 for note in notes for ec in user_ecs if ec.lower() in note.lower())
    base = 1 if len(user_ecs) >= 3 else 0
    return round(min(base + matches * 0.5, max_bonus), 1)


def _find_official(official, school, program, matched_programs):
    """Official range for the program the user means, if the profiles have one."""
    ranges = official.get(school) or {}
    if not ranges:
        return None, None
    name = schools.best_program_match(program, ranges.keys(), school)
    if name is None:
        pk = _key(program)
        hits = [n for n in ranges if pk and pk in _key(n)]
        hits += [n for n in ranges if n in matched_programs and n not in hits]
        name = min(hits, key=len) if hits else None
    return (name, ranges[name]) if name else (None, None)


def _range_bounds(rng):
    low = float(rng["low"])
    high = rng.get("high")
    high = float(high) if high is not None else min(low + 5.0, 100.0)
    return low, max(low, high)


def predict_admission_chance(rows, school, program, user_avg, user_ecs=None, programs=None):
    """Return a dict describing the estimate, or {'found': False, ...}.

    `programs` (optional) are program profiles; their facts.admission_range
    is used when crowd-sourced offers are scarce.
    """
    user_ecs = user_ecs or []
    official = _official_index(programs)
    resolved = resolve_school(rows, school, programs)
    if resolved is None:
        return {"found": False, "reason": "school",
                "message": f"We don't have admissions data for “{school}” yet."}

    pk = _key(program)
    offers = [r for r in rows if r["University"] == resolved and pk in _key(r["Program name"])]
    matched_programs = sorted({r["Program name"] for r in offers})
    official_name, official_range = _find_official(official, resolved, program, matched_programs)
    if not offers and official_range is None:
        return {"found": False, "reason": "program",
                "message": f"No past offers found for “{program}” at {resolved}."}

    # Crowd statistics, weighting recent cycles more.
    years = [r.get("year") for r in offers if r.get("year")]
    newest = max(years) if years else None
    weights = [RECENCY_DECAY ** (newest - r["year"]) if newest and r.get("year") else 1.0 for r in offers]
    n_eff = sum(weights)
    if offers:
        crowd_avg = sum(w * r["avg"] for w, r in zip(weights, offers)) / n_eff
        crowd_min, crowd_max = min(r["avg"] for r in offers), max(r["avg"] for r in offers)

    if official_range is None:
        basis = "crowd"
        avg_accept, min_accept, max_accept = crowd_avg, crowd_min, crowd_max
    else:
        o_low, o_high = _range_bounds(official_range)
        o_mid = (o_low + o_high) / 2
        if not offers:
            basis, alpha = "official", 0.0
        elif n_eff >= MIN_CROWD:
            basis, alpha = "crowd", 1.0
        else:
            basis, alpha = "blended", n_eff / MIN_CROWD
        if alpha == 0.0:
            avg_accept, min_accept, max_accept = o_mid, o_low, o_high
        elif alpha == 1.0:
            avg_accept, min_accept, max_accept = crowd_avg, crowd_min, crowd_max
        else:
            avg_accept = alpha * crowd_avg + (1 - alpha) * o_mid
            min_accept = alpha * crowd_min + (1 - alpha) * o_low
            max_accept = alpha * crowd_max + (1 - alpha) * o_high
        min_accept = min(min_accept, avg_accept)
        max_accept = max(max_accept, avg_accept)
        if official_name and official_name not in matched_programs:
            matched_programs = sorted(set(matched_programs) | {official_name})

    supp_required = any(r.get("Supp App?") for r in offers)

    ec_bonus = 0
    if supp_required and user_ecs:
        notes = [f"{r.get('Notable info from supp app', '')} {r.get('Comments', '')}" for r in offers]
        ec_bonus = _ec_bonus(user_ecs, notes)
    adjusted = user_avg + ec_bonus

    if adjusted >= max_accept:
        score, verdict = 95 + (adjusted - max_accept), "Very likely"
    elif adjusted >= avg_accept:
        span = max_accept - avg_accept
        score, verdict = 75 + ((adjusted - avg_accept) / span) * 19 if span else 75, "Likely"
    elif adjusted >= min_accept:
        span = avg_accept - min_accept
        score, verdict = 50 + ((adjusted - min_accept) / span) * 24 if span else 50, "Possible, but below average"
    else:
        score, verdict = max(10, (adjusted / min_accept) * 40), "Unlikely"

    by_year = {}
    for r in offers:
        y = str(r.get("year") or "unknown")
        by_year[y] = by_year.get(y, 0) + 1

    return {
        "found": True,
        "school": resolved,
        "program": program,
        "matched_programs": matched_programs,
        "sample_size": len(offers),
        "low_confidence": len(offers) < LOW_CONFIDENCE,
        "supp_required": supp_required,
        "user_average": user_avg,
        "ec_bonus": ec_bonus,
        "adjusted_average": round(adjusted, 1),
        "offer_average": round(avg_accept, 1),
        "offer_min": round(min_accept, 1),
        "offer_max": round(max_accept, 1),
        "chance": min(round(score, 1), 99.0),
        "verdict": verdict,
        # Added in the 2026-11 data refresh
        "basis": basis,
        "effective_sample_size": round(n_eff, 2),
        "offers_by_year": dict(sorted(by_year.items())),
        "official_range": (
            {"program": official_name, "text": official_range.get("text"),
             "low": official_range.get("low"), "high": official_range.get("high"),
             "source_url": official_range.get("source_url")}
            if official_range else None),
    }
