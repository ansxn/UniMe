"""ChanceMe: estimate admission chances from crowd-sourced past offers."""
import csv
import re

# Full / common names -> the short names used in admissionsData.csv.
# Keys are compared after lowercasing and collapsing punctuation (see _key).
SCHOOL_ALIASES = {
    "university of waterloo": "Waterloo", "uwaterloo": "Waterloo", "uw": "Waterloo",
    "mcmaster university": "McMaster", "mac": "McMaster",
    "western university": "Western", "university of western ontario": "Western",
    "uwo": "Western", "western": "Western",
    "huron university college": "Western - Huron", "western huron": "Western - Huron",
    "university of toronto": "UofT - SG", "uoft": "UofT - SG", "u of t": "UofT - SG",
    "uoft st george": "UofT - SG", "university of toronto st george": "UofT - SG",
    "university of toronto scarborough": "UTSc", "uoft scarborough": "UTSc", "utsc": "UTSc",
    "university of toronto mississauga": "UTM", "uoft mississauga": "UTM", "utm": "UTM",
    "university of ottawa": "UOttawa", "uottawa": "UOttawa", "ottawa": "UOttawa",
    "queens university": "Queen's", "queens": "Queen's",
    "wilfrid laurier university": "Laurier", "laurier": "Laurier", "wlu": "Laurier",
    "toronto metropolitan university": "TMU", "ryerson": "TMU", "ryerson university": "TMU",
    "york university": "York", "york": "York",
    "university of guelph": "Guelph", "guelph": "Guelph",
    "university of guelph humber": "Guelph-Humber", "guelph humber": "Guelph-Humber",
    "carleton university": "Carleton", "brock university": "Brock",
    "mcgill university": "McGill", "ontario tech university": "Ontario Tech", "uoit": "Ontario Tech",
    "trent university": "Trent", "university of british columbia": "UBC",
    "lakehead university": "Lakehead", "laurentian university": "Laurentian",
    "dalhousie university": "Dalhousie", "university of windsor": "Windsor",
    "ocad university": "OCAD", "nipissing university": "Nipissing",
    "concordia university": "Concordia", "university of victoria": "UVIC",
}

MIN_SCHOOL_ROWS = 3  # schools with fewer offers aren't offered in the dropdown

_AVG_RE = re.compile(r"^\s*~?\s*(\d{2,3}(?:\.\d+)?)\s*%?\s*(?:\(top ?6\))?\s*$", re.I)


def _key(s):
    s = str(s or "").lower().replace("’", "'").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _parse_avg(raw):
    m = _AVG_RE.match(str(raw or ""))
    if not m:
        return None
    val = float(m.group(1))
    return val if 50 <= val <= 100 else None


def load_admissions(path):
    """Return offer rows as dicts with a parsed numeric 'avg'."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if row.get("Decision", "").lower() != "offer":
                continue  # also skips the metadata line under the header
            avg = _parse_avg(row.get("Top 6 Average"))
            if avg is None:
                continue
            row["avg"] = avg
            rows.append(row)
    return rows


def resolve_school(rows, school):
    """Map user input to a school name present in the data, or None."""
    names = {r["University"] for r in rows}
    k = _key(school)
    for name in names:
        if _key(name) == k:
            return name
    alias = SCHOOL_ALIASES.get(k)
    return alias if alias in names else None


def chance_options(rows):
    """Schools (with enough data) and the program names seen for each."""
    by_school = {}
    for r in rows:
        by_school.setdefault(r["University"], set()).add(r["Program name"])
    return [
        {"school": s, "programs": sorted(p)}
        for s, p in sorted(by_school.items())
        if sum(1 for r in rows if r["University"] == s) >= MIN_SCHOOL_ROWS
    ]


def _ec_bonus(user_ecs, notes, max_bonus=3):
    """+1 for 3+ ECs, +0.5 per EC mentioned in past applicants' notes, capped."""
    matches = sum(1 for note in notes for ec in user_ecs if ec.lower() in note.lower())
    base = 1 if len(user_ecs) >= 3 else 0
    return round(min(base + matches * 0.5, max_bonus), 1)


def predict_admission_chance(rows, school, program, user_avg, user_ecs=None):
    """Return a dict describing the estimate, or {'found': False, ...}."""
    user_ecs = user_ecs or []
    resolved = resolve_school(rows, school)
    if resolved is None:
        return {"found": False, "reason": "school",
                "message": f"We don't have admissions data for “{school}” yet."}

    pk = _key(program)
    offers = [r for r in rows if r["University"] == resolved and pk in _key(r["Program name"])]
    if not offers:
        return {"found": False, "reason": "program",
                "message": f"No past offers found for “{program}” at {resolved}."}

    avgs = [r["avg"] for r in offers]
    avg_accept, min_accept, max_accept = sum(avgs) / len(avgs), min(avgs), max(avgs)
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

    return {
        "found": True,
        "school": resolved,
        "program": program,
        "matched_programs": sorted({r["Program name"] for r in offers}),
        "sample_size": len(offers),
        "low_confidence": len(offers) < 5,
        "supp_required": supp_required,
        "user_average": user_avg,
        "ec_bonus": ec_bonus,
        "adjusted_average": round(adjusted, 1),
        "offer_average": round(avg_accept, 1),
        "offer_min": round(min_accept, 1),
        "offer_max": round(max_accept, 1),
        "chance": min(round(score, 1), 99.0),
        "verdict": verdict,
    }
