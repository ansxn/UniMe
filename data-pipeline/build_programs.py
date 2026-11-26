"""Build frontend/api/_unime/data/program_profiles.json.

Steps
  1. Probe OUInfo (official catalogue). As of 2026-11-25 it is not scrapable
     (robots.txt blocks Anthropic's agents and every page is behind a
     Cloudflare bot challenge), so the probe only reports status.
  2. Load the June 2025 profiles (baseline/program_profiles_2025-06.json),
     canonicalize school names, drop duplicates.
  3. Merge optional official facts from manual/official_programs.csv (see
     README). Rows that match an existing program add facts to it; rows that
     don't become new programs with derived traits.
  4. Add a `facts` object to every program (city, degree, co-op, prereqs,
     admission range, sources) and fill empty campus/social objects from
     universities.json.
  5. Record where every section's values came from in `trait_source`.

Usage:  python build_programs.py [--refresh] [--skip-probe]
"""
import argparse
import collections
import csv
import json
import os
import re
import statistics
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "frontend", "api"))

import fetch  # noqa: E402
import sources  # noqa: E402
from _unime import schools  # noqa: E402

BASELINE = os.path.join(HERE, "baseline", "program_profiles_2025-06.json")
UNIVERSITIES = os.path.join(HERE, "universities.json")
OFFICIAL_CSV = os.path.join(HERE, "manual", "official_programs.csv")
OUT = os.path.join(HERE, "..", "frontend", "api", "_unime", "data", "program_profiles.json")

TRAITS = ["learning_style", "first_year_specialization", "coop_importance", "research_importance",
          "creativity_orientation", "career_certainty", "math_enjoyment", "collaboration_preference"]


# ---------------------------------------------------------------------------
# Official-catalogue probe
# ---------------------------------------------------------------------------
def probe_ouinfo(log=print):
    url = sources.OUINFO_BASE + "/programs"
    try:
        if not fetch.robots_allows(url):
            return "blocked: robots.txt disallows or challenges automated clients"
        fetch.fetch(url, refresh=True)
        return "reachable (scraper not implemented; see README before adding one)"
    except fetch.Blocked as e:
        return f"blocked: {e}"
    except Exception as e:  # noqa: BLE001
        return f"unreachable: {e.__class__.__name__}: {e}"


# ---------------------------------------------------------------------------
# Fact parsing (all deterministic)
# ---------------------------------------------------------------------------
_DEGREE_RE = re.compile(
    r"\b(BASc|BSc(?:N)?|BA|BBA|BCom|BEng|BMath|BES|BFA|BKin|BMus|BSW|BEd|BHSc|BTech|BDes|BArch|BPHE|BJ|BIT|BCS|BAS|"
    r"Bachelor of [A-Z][A-Za-z&' ]+?)(?=[)\],;/]|\s*$|\s+(?:with|in)\b|\s+and\s+[A-Z][a-z]+ of\b)")


def parse_degree(program_name):
    m = _DEGREE_RE.search(program_name)
    return m.group(1).strip() if m else None


def coop_from_name(program_name):
    """'only' | 'available' | None (unknown) from an official program title."""
    k = schools.key(program_name)
    if not re.search(r"\bco ?op\b", k):
        return None
    if re.search(r"\bco ?op only\b|\bco ?op required\b|\bmandatory co ?op\b", k):
        return "only"
    return "available"


_BAND = {"low": (0, 3), "mid": (3, 7), "high": (7, 10)}


def parse_admission_range(text):
    """Parse OUInfo-style grade ranges into {text, low, high} (high may be None).

    "Low 90s" -> 90-93, "Mid-to-high 80s" -> 83-90, "85-90%" -> 85-90,
    "80%+" / "80% or higher" -> 80-None, "75%" -> 75-75.
    """
    t = str(text or "").strip()
    if not t:
        return None
    s = t.lower().replace("–", "-").replace("’", "'")
    m = re.search(r"(low|mid|high)(?:\s*-?\s*(?:to|-)\s*-?\s*(low|mid|high))?\s*-?\s*(\d)0'?s", s)
    if m:
        a, b, dec = m.group(1), m.group(2) or m.group(1), int(m.group(3)) * 10
        return {"text": t, "low": dec + _BAND[a][0], "high": min(dec + _BAND[b][1], 100)}
    nums = [float(x) for x in re.findall(r"\d{2,3}(?:\.\d+)?", s)]
    nums = [n for n in nums if 50 <= n <= 100]
    if not nums:
        return None
    if len(nums) >= 2:
        return {"text": t, "low": min(nums[:2]), "high": max(nums[:2])}
    if "+" in s or "higher" in s or "above" in s or "minimum" in s:
        return {"text": t, "low": nums[0], "high": None}
    return {"text": t, "low": nums[0], "high": nums[0]}


_MATH_PREREQS = {"MCV4U": 5, "MHF4U": 4, "MDM4U": 3, "MCR3U": 3}


def math_from_prereqs(prereqs):
    if prereqs is None:
        return None
    codes = {p.strip().upper()[:5] for p in prereqs}
    levels = [v for c, v in _MATH_PREREQS.items() if c in codes]
    text = " ".join(prereqs).lower()
    if not levels and ("calculus" in text):
        levels = [5]
    elif not levels and ("advanced functions" in text or "math" in text):
        levels = [4]
    return max(levels) if levels else 2


_COURSE_FROM_PREREQ = {
    "MCV4U": "Calculus", "MHF4U": "Mathematics", "MDM4U": "Statistics", "SPH4U": "Physics",
    "SCH4U": "Chemistry", "SBI4U": "Biology", "ENG4U": "English", "ICS4U": "Computer Science",
    "BBB4M": "Business Studies", "CIA4U": "Economics", "HSB4U": "Social Sciences",
    "CHY4U": "History", "CGW4U": "Geography", "AVI4M": "Visual Arts", "AMU4M": "Music",
    "ADA4M": "Drama", "FSF4U": "French", "PSE4U": "Physical Education",
}


# ---------------------------------------------------------------------------
# Trait derivation for programs that are not in the baseline
# ---------------------------------------------------------------------------
# keyword in program name -> (interests, liked_hs_courses, trait overrides)
_HEURISTICS = [
    ("engineering", ["Engineering", "Mathematics", "Physics", "Design"], ["Mathematics", "Physics", "Chemistry"],
     dict(learning_style=4, first_year_specialization=4, math_enjoyment=5, career_certainty=4,
          collaboration_preference=4, research_importance=3, creativity_orientation=3)),
    ("computer", ["Computer Science", "Programming", "Mathematics", "Technology"], ["Mathematics", "Computer Science"],
     dict(learning_style=4, first_year_specialization=4, math_enjoyment=5, career_certainty=4)),
    ("software", ["Software Development", "Programming", "Computer Science"], ["Mathematics", "Computer Science"],
     dict(learning_style=4, first_year_specialization=4, math_enjoyment=5, career_certainty=4)),
    ("math", ["Mathematics", "Statistics"], ["Mathematics", "Calculus"],
     dict(math_enjoyment=5, research_importance=3, learning_style=2)),
    ("nursing", ["Nursing", "Healthcare", "Health Sciences"], ["Biology", "Chemistry"],
     dict(learning_style=5, first_year_specialization=5, career_certainty=5, collaboration_preference=4,
          math_enjoyment=2)),
    ("health", ["Health Sciences", "Healthcare", "Biology"], ["Biology", "Chemistry"],
     dict(research_importance=4, collaboration_preference=4, math_enjoyment=3)),
    ("kinesiology", ["Kinesiology", "Health Sciences", "Physiology"], ["Biology", "Physical Education"],
     dict(learning_style=4, math_enjoyment=2, collaboration_preference=4)),
    ("business", ["Business", "Management", "Finance"], ["Business Studies", "Mathematics", "Economics"],
     dict(collaboration_preference=4, career_certainty=4, math_enjoyment=3, research_importance=2)),
    ("commerce", ["Business", "Commerce", "Finance"], ["Business Studies", "Mathematics"],
     dict(collaboration_preference=4, career_certainty=4, math_enjoyment=3, research_importance=2)),
    ("accounting", ["Accounting", "Finance", "Business"], ["Mathematics", "Business Studies"],
     dict(career_certainty=5, math_enjoyment=4, creativity_orientation=2, research_importance=2)),
    ("economics", ["Economics", "Finance", "Business"], ["Economics", "Mathematics"],
     dict(math_enjoyment=4, research_importance=3)),
    ("education", ["Education", "Teaching"], ["English", "Social Studies"],
     dict(career_certainty=5, collaboration_preference=4, first_year_specialization=4, math_enjoyment=2)),
    ("law", ["Law", "Justice", "Policy"], ["History", "Law", "English"],
     dict(research_importance=3, math_enjoyment=2)),
    ("criminology", ["Criminology", "Justice", "Sociology"], ["Law", "Social Sciences"],
     dict(math_enjoyment=2)),
    ("psychology", ["Psychology", "Human Behavior", "Research"], ["Psychology", "Biology"],
     dict(research_importance=4, math_enjoyment=3)),
    ("biology", ["Biology", "Life Science", "Research"], ["Biology", "Chemistry"],
     dict(research_importance=4, math_enjoyment=3, learning_style=3)),
    ("chemistry", ["Chemistry", "Science", "Research"], ["Chemistry", "Mathematics"],
     dict(research_importance=4, math_enjoyment=4)),
    ("physics", ["Physics", "Mathematics", "Science"], ["Physics", "Mathematics", "Calculus"],
     dict(research_importance=4, math_enjoyment=5)),
    ("science", ["Science", "Research"], ["Biology", "Chemistry", "Mathematics"],
     dict(research_importance=4, math_enjoyment=3)),
    ("design", ["Design", "Arts", "Media"], ["Visual Arts", "Design"],
     dict(creativity_orientation=5, learning_style=4, math_enjoyment=2)),
    ("art", ["Arts", "Fine Art", "Visual Arts"], ["Visual Arts", "Art"],
     dict(creativity_orientation=5, learning_style=4, math_enjoyment=1, career_certainty=2)),
    ("music", ["Music", "Arts", "Performance"], ["Music"],
     dict(creativity_orientation=5, learning_style=4, math_enjoyment=2)),
    ("media", ["Media", "Communication", "Film"], ["Media Studies", "English"],
     dict(creativity_orientation=4, math_enjoyment=2)),
    ("history", ["History", "Humanities", "Research"], ["History", "English"],
     dict(research_importance=4, math_enjoyment=1, career_certainty=2)),
    ("english", ["Literature", "Writing", "Humanities"], ["English", "English Literature"],
     dict(creativity_orientation=4, math_enjoyment=1, career_certainty=2)),
    ("political", ["Political Science", "Politics", "Policy"], ["History", "Social Studies"],
     dict(research_importance=3, math_enjoyment=2)),
    ("social work", ["Social Work", "Social Justice", "Community"], ["Social Sciences", "Sociology"],
     dict(career_certainty=5, collaboration_preference=5, math_enjoyment=1)),
    ("sociology", ["Sociology", "Social Sciences", "Social Issues"], ["Sociology", "Social Sciences"],
     dict(math_enjoyment=2, research_importance=3)),
    ("environment", ["Environmental Science", "Sustainability", "Ecology"], ["Biology", "Geography"],
     dict(research_importance=4, learning_style=4)),
    ("geography", ["Geography", "Environmental Science"], ["Geography"], dict(learning_style=4)),
    ("arts", ["Arts", "Humanities", "Social Sciences"], ["English", "History"],
     dict(first_year_specialization=2, career_certainty=2, math_enjoyment=2)),
]
_DEFAULT_TRAITS = dict(learning_style=3, first_year_specialization=3, coop_importance=3, research_importance=3,
                       creativity_orientation=3, career_certainty=3, math_enjoyment=3, collaboration_preference=3)


def derive_academic(program_name, facts, reference_programs):
    """Deterministic academic traits for a program with no carried-over values.

    1. If programs with the same core name exist at other schools (e.g. a new
       "Computer Science" program), use the per-trait median of those and the
       most common interests/courses -> trait_source "derived:similar_program".
    2. Otherwise use the first matching keyword rule in _HEURISTICS on top of
       neutral 3s -> "derived:heuristic".
    3. In both cases official facts override: coop_importance from co-op
       availability (only=5, available=4, none=2) and math_enjoyment from math
       prerequisites (MCV4U=5, MHF4U=4, MDM4U/other=3, none=2); prerequisite
       courses are added to liked_hs_courses.
    """
    toks, _ = schools.program_tokens(program_name)
    similar = [p for p in reference_programs if schools.program_tokens(p["program"])[0] == toks] if toks else []
    if similar:
        acad = {t: int(statistics.median_low(sorted(p["academic"].get(t, 3) for p in similar))) for t in TRAITS}
        for f in ("interests", "liked_hs_courses", "alt_to_engineering"):
            acad[f] = json.loads(collections.Counter(
                json.dumps(p["academic"].get(f, [])) for p in similar).most_common(1)[0][0])
        source = "derived:similar_program"
    else:
        acad = dict(_DEFAULT_TRAITS)
        acad.update(interests=[], liked_hs_courses=[], alt_to_engineering=[])
        name = program_name.lower()
        for kw, interests, courses, overrides in _HEURISTICS:
            if re.search(rf"\b{re.escape(kw)}", name):
                acad.update(overrides)
                acad["interests"], acad["liked_hs_courses"] = list(interests), list(courses)
                break
        if not acad["interests"]:
            acad["interests"] = [w for w in re.findall(r"[A-Z][a-z]+", program_name)][:3]
        source = "derived:heuristic"

    coop = facts.get("coop")
    if coop:
        acad["coop_importance"] = {"only": 5, "available": 4, "none": 2}[coop]
    math = math_from_prereqs(facts.get("prerequisites"))
    if math is not None:
        acad["math_enjoyment"] = math
    for code in facts.get("prerequisites") or []:
        course = _COURSE_FROM_PREREQ.get(code.strip().upper()[:5])
        if course and course not in acad["liked_hs_courses"]:
            acad["liked_hs_courses"].append(course)
    return acad, source


# ---------------------------------------------------------------------------
def load_official(path=OFFICIAL_CSV):
    """manual/official_programs.csv -> list of dicts (empty if the file is absent)."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
            uni = schools.canonical(r.get("uni", ""))
            if not uni or not r.get("program"):
                continue
            coop = r.get("coop", "").lower() or None
            if coop not in (None, "only", "available", "none"):
                coop = None
            prereqs = [p.strip() for p in r.get("prerequisites", "").split(";") if p.strip()] or None
            out.append({
                "uni": uni, "program": " ".join(r["program"].split()),
                "campus_name": r.get("campus") or None, "degree": r.get("degree") or None,
                "coop": coop, "prerequisites": prereqs,
                "admission_range": parse_admission_range(r.get("admission_range")),
                "source_url": r.get("source_url") or None, "retrieved": r.get("retrieved") or None,
            })
    return out


def build(skip_probe=False, log=print, official_path=OFFICIAL_CSV):
    status = "not checked (--skip-probe)" if skip_probe else probe_ouinfo(log)
    log(f"  OUInfo: {status}")
    with open(UNIVERSITIES, encoding="utf-8") as f:
        unis = json.load(f)["universities"]
    with open(BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)

    programs, seen = [], set()
    for p in baseline:
        p = json.loads(json.dumps(p))
        p["uni"] = schools.clean_name(p["uni"])
        p["program"] = " ".join(re.sub("[\u200b\u00ad\ufeff]", "", p["program"]).split())
        k = (p["uni"], p["program"])
        if k in seen:
            continue
        seen.add(k)
        programs.append(p)
    n_baseline_raw, n_baseline = len(baseline), len(programs)
    empty_campus_before = sum(1 for p in programs if not p.get("campus"))
    reference = list(programs)  # for derivation: carried-over programs only

    official = load_official(official_path)
    by_uni = collections.defaultdict(dict)
    for p in programs:
        by_uni[p["uni"]][p["program"]] = p
        coop = coop_from_name(p["program"])
        p["facts"] = {"coop": coop}
        p["trait_source"] = {"academic": "carried_over", "campus": "carried_over", "social": "carried_over"}
        p["source"] = {"catalogue": "unime-2025-06", "facts": "program-title" if coop else None}

    added = merged = 0
    for o in official:
        match = schools.best_program_match(o["program"], by_uni[o["uni"]].keys(), o["uni"])
        if match:
            p = by_uni[o["uni"]][match]
            merged += 1
        else:
            p = {"uni": o["uni"], "program": o["program"], "facts": {"coop": o["coop"]},
                 "trait_source": {}, "source": {"catalogue": "official"}}
            acad, src = derive_academic(o["program"], o, reference)
            p["academic"], p["campus"], p["social"] = acad, {}, {}
            p["trait_source"]["academic"] = src
            programs.append(p)
            by_uni[o["uni"]][o["program"]] = p
            added += 1
        f = p["facts"]
        for k in ("campus_name", "degree", "prerequisites", "admission_range", "source_url", "retrieved"):
            if o.get(k) is not None:
                f[k] = o[k]
        if o["coop"]:
            f["coop"] = o["coop"]
        p["source"]["facts"] = "official"

    filled = 0
    for p in programs:
        u = unis.get(p["uni"], {})
        f = p["facts"]
        f.setdefault("degree", parse_degree(p["program"]))
        f["coop_available"] = {"only": True, "available": True, "none": False}.get(f.get("coop"))
        f["coop_required"] = True if f.get("coop") == "only" else (False if f.get("coop") else None)
        f.pop("coop", None)
        f.setdefault("prerequisites", None)
        f.setdefault("admission_range", None)
        f.setdefault("source_url", None)
        f["city"] = u.get("city")
        f.setdefault("campus_name", None)
        f["university_url"] = u.get("official_url")
        for section in ("campus", "social"):
            if not p.get(section) and u.get(section):
                p[section] = json.loads(json.dumps(u[section]))
                p["trait_source"][section] = f"university_table:{u.get('values_source')}"
                filled += section == "campus"
            p["trait_source"].setdefault(section, "missing" if not p.get(section) else "carried_over")
        p["facts"] = dict(sorted(f.items()))

    programs.sort(key=lambda p: (p["uni"], p["program"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(programs, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    stats = {
        "built": date.today().isoformat(), "ouinfo_status": status,
        "baseline_rows": n_baseline_raw, "baseline_after_dedupe": n_baseline,
        "official_rows": len(official), "official_merged": merged, "official_added": added,
        "programs": len(programs), "empty_campus_before": empty_campus_before,
        "empty_campus_filled": filled, "empty_campus_after": sum(1 for p in programs if not p.get("campus")),
        "with_admission_range": sum(1 for p in programs if p["facts"]["admission_range"]),
        "with_coop_known": sum(1 for p in programs if p["facts"]["coop_available"] is not None),
        "with_degree": sum(1 for p in programs if p["facts"]["degree"]),
    }
    return programs, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-probe", action="store_true", help="don't contact OUInfo at all")
    args = ap.parse_args()
    print("Building program profiles...")
    _, stats = build(args.skip_probe)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"Wrote {os.path.relpath(OUT, HERE)}")
