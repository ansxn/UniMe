"""Build frontend/api/_unime/data/admissionsData.csv from crowd-sourced sheets.

Inputs (per cycle, first one found wins):
  1. manual/<cycle>.csv        -- a CSV export you placed by hand (e.g. given
                                  to you by the sheet owner)
  2. the public Google Sheet's CSV export (sources.ADMISSIONS_SHEETS), cached
  3. baseline/admissions_<cycle>_legacy.csv -- the file UniMe shipped with
     (2024-2025 cycle only)

Output columns (the first seven are what the API has always read):
  University, Program name, Decision, Top 6 Average, Supp App?,
  Notable info from supp app, Comments, year, cycle, source

Personal data (timestamps, Reddit/Discord usernames, citizenship, free-text
comments from the form) is never written to the output.

Usage:  python build_admissions.py [--refresh]
"""
import argparse
import collections
import csv
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "frontend", "api"))

import fetch  # noqa: E402
import sources  # noqa: E402
from _unime import schools  # noqa: E402

DATA = os.path.join(HERE, "..", "frontend", "api", "_unime", "data")
OUT = os.path.join(DATA, "admissionsData.csv")
PROFILES = os.path.join(DATA, "program_profiles.json")
OUT_COLUMNS = ["University", "Program name", "Decision", "Top 6 Average", "Supp App?",
               "Notable info from supp app", "Comments", "year", "cycle", "profile_match", "source"]

# ---------------------------------------------------------------------------
# Field parsing
# ---------------------------------------------------------------------------
_NUM = r"(\d{2,3}(?:[.,]\d+)?)"
_RANGE_RE = re.compile(rf"^{_NUM}\s*(?:-|–|to|/)\s*{_NUM}$")
_NUM_RE = re.compile(_NUM)
_NOT_PERCENT = re.compile(r"(\bgpa\b|\bib\b|/\s*45|out of 45|\bsat\b|\bact\b|\bcgpa\b|r-?score|cegep|/\s*4\.?0?\b)", re.I)


_BAND_RE = re.compile(r"^(low|mid|high)\s*(?:to\s*mid\s*)?(\d)0'?s$")
_BAND_OFFSET = {"low": 2, "mid": 5, "high": 8}
_TOP6_RE = re.compile(r"top\s*6\s*[:=-]?\s*" + _NUM)
_QUALIFIERS = re.compile(
    r"\b(around|approx\.?|approximately|about|roughly|like|ish|i think|maybe|avg|average|"
    r"percent|top ?6|top ?5|gr\.? ?1[12]|grade ?1[12]|midterms?|finals?|predicted|current|overall|"
    r"of|an?|my|was|with|all|prereqs?)\b")


def parse_average(raw):
    """Parse a self-reported top-6 average into a float in [60, 100], or None.

    Accepts "93", "93.5%", "~94", "94 (top 6)", "93,5", "92-93" (midpoint, if
    within 5 points), "94ish", "95 gr 12 midterm", "Top 5: 97.4, Top 6: 97.8"
    (takes the top-6 figure) and grade bands ("low 90s" = 92, "mid 80s" = 85,
    "high 80s" = 88). Rejects IB points, GPAs, CEGEP R-scores, lists of
    several marks, and anything outside 60-100.
    """
    s = str(raw or "").strip().lower().replace("’", "'")
    if not s or _NOT_PERCENT.search(s):
        return None
    m = _TOP6_RE.search(s)
    if m:
        val = float(m.group(1).replace(",", "."))
        return round(val, 2) if 60 <= val <= 100 else None
    s = re.sub(r"\(.*?\)", " ", s)  # "(top 6)", "(midterm)"
    s = s.replace("%", " ").replace("~", " ").replace("≈", " ").replace("?", " ")
    s = re.sub(r"(\d)\s*ish\b", r"\1", s)
    s = _QUALIFIERS.sub(" ", s)
    s = " ".join(s.split()).strip(" :.-=,")
    m = _BAND_RE.match(s)
    if m:
        val = int(m.group(2)) * 10 + _BAND_OFFSET[m.group(1)]
        return float(val) if 60 <= val <= 100 else None
    m = _RANGE_RE.match(s)
    if m:
        a, b = (float(x.replace(",", ".")) for x in m.groups())
        val = (a + b) / 2 if abs(a - b) <= 5 else None
    else:
        if not re.fullmatch(_NUM, s):
            return None
        val = float(s.replace(",", "."))
    if val is None or not 60 <= val <= 100:
        return None
    return round(val, 2)


def normalize_decision(raw):
    s = str(raw or "").strip().lower()
    if not s:
        return None
    if s.startswith(("accept", "offer", "admit", "conditional")) or s in ("yes", "accepted"):
        return "Offer"
    if s.startswith(("reject", "refus", "denied", "declin")):
        return "Rejected"
    if s.startswith("defer") or "deferred" in s:
        return "Deferred"
    if s.startswith("wait") or "waitlist" in s:
        return "Waitlisted"
    if "accept" in s or "offer" in s:
        return "Offer"
    return None


_HANDLE_RE = re.compile(r"(@\S+|\b\S+#\d{4}\b|\bu/\S+|\bdiscord\b.*$|\breddit\b.*$)", re.I)
_EMPTY_NOTES = {"", "n/a", "na", "none", "no", "nope", "nah", "-", ".", "nil", "nothing", "x"}


def clean_note(raw):
    """Keep EC notes (used for the ChanceMe EC bonus); drop handles and empties."""
    s = " ".join(str(raw or "").split())
    s = _HANDLE_RE.sub("", s).strip()
    return "" if s.lower().strip(" .!") in _EMPTY_NOTES else s[:500]


_SCHOOL_PREFIX_RE = re.compile(r"^(?P<school>[^-|:]{3,60}?)\s*[-:|]\s+(?P<rest>.+)$")


def clean_program(raw, school):
    s = " ".join(str(raw or "").replace("\u2013", "-").replace("\u2014", "-").split()).strip(" -,.")
    m = _SCHOOL_PREFIX_RE.match(s)
    if m and schools.canonical(m.group("school")):
        s = m.group("rest")  # "McMaster University - Health Sciences" -> "Health Sciences"
    if school and school.startswith("University of Toronto"):
        # campus is encoded in the canonical school name
        s = re.sub(r"\s*[-(,]?\s*\b(st\.? ?george|utsg|sg|utm|mississauga|utsc|scarborough)\b(\s*campus)?\)?\s*$",
                   "", s, flags=re.I).strip(" -,")
    return s


_DEGREE_TOKENS = re.compile(
    r"\b(bsc|ba|bba|basc|bcom|beng|bmath|bhsc|bes|bfa|bas|bkin|bmus|bsw|bscn|bph|bed|bsc h|"
    r"hon|hons|honours|honors|honour|h|program|degree|major|i)\b")


def program_group_key(program):
    """Looser key used to merge spelling variants of the same program.

    Drops degree abbreviations and 'honours'; keeps 'coop' so co-op and
    regular streams stay separate.
    """
    k = schools.key(program).replace("co op", "coop")
    k2 = re.sub(r"\bbachelor of (arts|science|applied science)\b", " ", k)
    k2 = " ".join(_DEGREE_TOKENS.sub(" ", k2).split())
    return k2 or k


def is_junk_program(p):
    k = schools.key(p)
    return (not k or len(p) > 200 or "|" in p or len(k) < 3 or k in {"n a", "na", "none", "test", "idk", "e"}
            or not re.search(r"[a-z]{2}", k))


# ---------------------------------------------------------------------------
# Per-cycle readers -> dicts with raw_school, raw_program, raw_decision, raw_avg,
# supp, notes, comments, ontario (bool|None)
# ---------------------------------------------------------------------------
def _col(header, *needles):
    for i, h in enumerate(header):
        hl = h.lower()
        if all(n in hl for n in needles):
            return i
    return None


def read_generic(text):
    """Reads any of the known form layouts by matching header text."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    header = rows[0]
    c_school = _col(header, "university")
    c_prog = _col(header, "program name")
    if c_prog is None:
        c_prog = _col(header, "what program")
    c_dec = _col(header, "decision")
    if c_dec is None:
        c_dec = _col(header, "accepted, rejected")
    if c_dec is None:
        c_dec = _col(header, "were you accepted")
    c_avg = _col(header, "top 6 average")
    if c_avg is None:
        c_avg = _col(header, "acceptance average")
    if c_avg is None:
        c_avg = _col(header, "average when accepted")
    c_avg_fallback = _col(header, "grade 12 midterm")
    c_supp = _col(header, "supp app?")
    c_notes = _col(header, "notable info")
    if c_notes is None:
        c_notes = _col(header, "notable extra")
    c_comments = _col(header, "comments") if c_notes is not None else None
    if c_comments is not None and "discord" in header[c_comments].lower():
        c_comments = None  # 2022-23 form asked for usernames in this field
    c_prov = _col(header, "province")
    c_country = _col(header, "country of residence")
    c_type = _col(header, "101 or 105")

    def get(r, c):
        return r[c].strip() if c is not None and c < len(r) else ""

    out = []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        ontario = None
        prov, country, typ = get(r, c_prov).lower(), get(r, c_country).lower(), get(r, c_type).lower()
        if prov:
            ontario = prov.startswith("ont") or prov == "on"
        elif country:
            ontario = None if country.startswith("canada") else False
        elif typ.startswith("105"):
            ontario = False
        elif typ.startswith("101"):
            ontario = True
        avg = get(r, c_avg)
        if not avg and c_avg_fallback is not None:
            avg = get(r, c_avg_fallback)
        out.append({
            "raw_school": get(r, c_school), "raw_program": get(r, c_prog),
            "raw_decision": get(r, c_dec), "raw_avg": avg,
            "supp": get(r, c_supp), "notes": get(r, c_notes), "comments": get(r, c_comments),
            "ontario": ontario,
        })
    return out


def load_cycle(sheet, refresh=False, log=print):
    cycle = sheet["cycle"]
    manual = os.path.join(HERE, "manual", f"{cycle}.csv")
    if os.path.exists(manual):
        with open(manual, encoding="utf-8-sig") as f:
            return read_generic(f.read()), "manual-export"
    url = sources.sheet_csv_url(sheet)
    try:
        body = fetch.fetch(url, refresh=refresh)
        meta = fetch.cached_meta(url) or {}
        log(f"  {cycle}: google sheet {sheet['sheet_id']} (retrieved {meta.get('retrieved', '?')})")
        return read_generic(body.decode("utf-8-sig")), "google-sheet"
    except Exception as e:  # noqa: BLE001 - report and fall back
        log(f"  {cycle}: sheet export not available ({e.__class__.__name__}: {e})")
    legacy = os.path.join(HERE, "baseline", f"admissions_{cycle}_legacy.csv")
    if os.path.exists(legacy):
        with open(legacy, encoding="utf-8-sig") as f:
            return read_generic(f.read()), "unime-legacy-2025-06"
    return [], None


# ---------------------------------------------------------------------------
def load_profile_names(path=PROFILES):
    """{school: [program names]} from the built program_profiles.json."""
    import json
    names = collections.defaultdict(list)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for p in json.load(f):
                names[p["uni"]].append(p["program"])
    return names


def build(refresh=False, log=print):
    stats = collections.OrderedDict()
    profile_names = load_profile_names()
    match_cache = {}
    out_rows = []
    for sheet in sources.ADMISSIONS_SHEETS:
        raw, src = load_cycle(sheet, refresh, log)
        st = collections.Counter(raw=len(raw))
        seen = set()
        for r in raw:
            school = schools.canonical(r["raw_school"], r["raw_program"])
            if school is None:
                st["drop_unknown_school"] += 1
                continue
            if r["ontario"] is False:
                st["drop_non_ontario_applicant"] += 1
                continue
            program = clean_program(r["raw_program"], school)
            if is_junk_program(program):
                st["drop_junk_program"] += 1
                continue
            decision = normalize_decision(r["raw_decision"])
            if decision is None:
                st["drop_unknown_decision"] += 1
                continue
            avg = parse_average(r["raw_avg"])
            if avg is None:
                st["drop_unparseable_average"] += 1
                continue
            supp = r["supp"].strip()
            supp = "" if supp.lower() in _EMPTY_NOTES else supp[:60]
            notes, comments = clean_note(r["notes"]), clean_note(r["comments"])
            dedupe_key = (school, program_group_key(program), decision, avg, schools.key(notes))
            if dedupe_key in seen:
                st["drop_duplicate"] += 1
                continue
            seen.add(dedupe_key)
            mk = (school, program)
            if mk not in match_cache:
                match_cache[mk] = schools.best_program_match(program, profile_names.get(school, []), school)
            matched = match_cache[mk]
            st["matched_to_profile"] += bool(matched)
            out_rows.append({
                "University": school, "Program name": matched or program, "Decision": decision,
                "Top 6 Average": f"{avg:g}", "Supp App?": supp,
                "Notable info from supp app": notes, "Comments": comments,
                "year": sheet["year"], "cycle": sheet["cycle"], "profile_match": "1" if matched else "",
                "source": src or "",
            })
            st["kept"] += 1
        stats[sheet["cycle"]] = (src, st)

    # Use one spelling per (school, program key): the most common one.
    spellings = collections.defaultdict(collections.Counter)
    for r in out_rows:
        spellings[(r["University"], program_group_key(r["Program name"]))][r["Program name"]] += 1
    for r in out_rows:
        if r["profile_match"]:
            continue
        variants = spellings[(r["University"], program_group_key(r["Program name"]))]
        r["Program name"] = max(variants.items(), key=lambda kv: (kv[1], -len(kv[0]), kv[0]))[0]

    out_rows.sort(key=lambda r: (-r["year"], r["University"], r["Program name"].lower(), float(r["Top 6 Average"])))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(out_rows)
    return out_rows, stats


def summarize(rows, stats, log=print):
    for cycle, (src, st) in stats.items():
        log(f"  {cycle}: source={src}  " + ", ".join(f"{k}={v}" for k, v in st.items()))
    offers = [r for r in rows if r["Decision"] == "Offer"]
    groups = collections.Counter((r["University"], schools.key(r["Program name"])) for r in offers)
    ge5 = sum(1 for v in groups.values() if v >= 5)
    log(f"  total rows={len(rows)} offers={len(offers)} groups={len(groups)} "
        f">=5 offers: {ge5} ({100 * ge5 / max(len(groups), 1):.1f}%)")
    log("  rows by year: " + ", ".join(f"{y}={n}" for y, n in sorted(collections.Counter(r['year'] for r in rows).items())))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download instead of using the cache")
    args = ap.parse_args()
    print("Building admissions data...")
    rows, stats = build(args.refresh)
    summarize(rows, stats)
    print(f"Wrote {os.path.relpath(OUT, HERE)}")
