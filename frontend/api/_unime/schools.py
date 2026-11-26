"""Canonical university names shared by the API and the data pipeline.

Canonical names are the ones used in program_profiles.json (`uni`). The data
pipeline (data-pipeline/) imports this module so that admissions rows and
program profiles always agree on school names.
"""
import re

# Canonical name -> extra aliases (lowercase, punctuation-collapsed; see key()).
# The canonical name and its key() are always aliases of themselves.
CANONICAL = {
    # Ontario universities (and federated/affiliated colleges) in program_profiles.json
    "Algoma University": ["algoma"],
    "Brock University": ["brock"],
    "Carleton University": ["carleton"],
    "Lakehead University": ["lakehead"],
    "Laurentian University": ["laurentian"],
    "McMaster University": ["mcmaster", "mac", "mcmaster u"],
    "Nipissing University": ["nipissing"],
    "OCAD University": ["ocad", "ocad u", "ocadu"],
    "Ontario Tech University": ["ontario tech", "uoit", "ontario tech u", "university of ontario institute of technology"],
    "Queen's University": ["queens", "queens university", "queens u", "queen s university", "queen s"],
    "Royal Military College of Canada": ["rmc", "royal military college"],
    "Toronto Metropolitan University": [
        "tmu", "ryerson", "ryerson university", "toronto metropolitan universit",
        "toronto metropolitan university formerly ryerson university", "toronto metropolitan"],
    "Trent University": ["trent", "trent peterborough", "trent university peterborough"],
    "Trent University - Durham Greater Toronto Area": ["trent durham", "trent university durham", "trent durham gta"],
    "University of Guelph": ["guelph", "uoguelph", "u of g"],
    "University of Guelph-Humber": ["guelph humber", "university of guelph humber", "uofgh"],
    "University of Ottawa": ["uottawa", "ottawa", "ottawa university", "u of o", "uo"],
    "University of Ottawa - Saint Paul University": ["saint paul university", "saint paul", "st paul university"],
    "University of Toronto": [
        "uoft", "u of t", "uoft sg", "uoft st george", "university of toronto st george",
        "university of toronto st g", "uoft st g", "utsg", "u of t st george", "toronto"],
    "University of Toronto Mississauga": [
        "utm", "uoft mississauga", "uoft missisauga", "university of toronto mississauga", "mississauga",
        "u of t mississauga"],
    "University of Toronto Scarborough": [
        "utsc", "uoft scarborough", "university of toronto scarborough", "scarborough campus",
        "u of t scarborough"],
    "University of Waterloo": ["waterloo", "uwaterloo", "uw", "waterloo campus", "u of waterloo"],
    "University of Waterloo - Renison University College": ["renison", "renison university college"],
    "University of Waterloo - St. Jerome's University": ["st jeromes", "st jeromes university", "st jerome s university"],
    "University of Windsor": ["windsor", "uwindsor"],
    "Western University": ["western", "uwo", "university of western ontario", "western ivey aeo", "ivey"],
    "Western University - Huron University College": ["huron", "huron university college", "western huron", "huron at western"],
    "Western University - King's University College": ["kings university college", "western kings", "kings", "king s university college"],
    "Wilfrid Laurier University": ["laurier", "wlu", "wilfred laurier university", "wilfrid laurier"],
    "Wilfrid Laurier University - Brantford Campus": ["laurier brantford", "wlu brantford"],
    "Wilfrid Laurier University - Milton Campus": ["laurier milton", "wlu milton"],
    "York University": ["york", "yorku", "york u"],
    "York University - Glendon Campus": ["glendon", "york glendon", "glendon college"],
    "York University - Markham Campus": ["york markham", "markham campus"],
    # Out-of-province schools that Ontario applicants commonly report (ChanceMe only)
    "McGill University": ["mcgill"],
    "University of British Columbia": ["ubc", "ubcv", "ubc vancouver"],
    "Dalhousie University": ["dalhousie", "dal"],
    "Concordia University": ["concordia"],
    "University of Alberta": ["ualberta", "alberta", "u of a"],
    "University of Calgary": ["ucalgary", "calgary"],
    "University of Victoria": ["uvic", "victoria"],
    "Simon Fraser University": ["sfu", "simon fraser", "simon fraser university sfu"],
    "Memorial University of Newfoundland": ["memorial", "memorial university", "mun"],
    "St. Francis Xavier University": ["st francis xavier", "stfx"],
    "University of New Brunswick": ["unb"],
}


def key(s):
    """Lowercase, drop apostrophes, collapse every other non-alphanumeric run to a space."""
    s = str(s or "").lower().replace("’", "'").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


ALIASES = {}
for _name, _aliases in CANONICAL.items():
    ALIASES[key(_name)] = _name
    for _a in _aliases:
        ALIASES[key(_a)] = _name


def clean_name(s):
    """Normalize dashes/whitespace the way program_profiles.json is written."""
    s = str(s or "").replace("–", "-").replace("—", "-")
    s = " ".join(s.split())
    if s == "Toronto Metropolitan University (formerly Ryerson University)":
        s = "Toronto Metropolitan University"
    return s


def canonical(raw, program=""):
    """Map a raw school string to a canonical name, or None if unknown.

    `program` is used to split University of Toronto rows by campus when the
    school column just says "University of Toronto".
    """
    name = ALIASES.get(key(clean_name(raw)))
    if name == "University of Toronto" and program:
        pk = key(program)
        if re.search(r"\b(utm|mississauga)\b", pk):
            return "University of Toronto Mississauga"
        if re.search(r"\b(utsc|scarborough)\b", pk):
            return "University of Toronto Scarborough"
    return name


# ---------------------------------------------------------------------------
# Program-name matching (crowd-sourced free text <-> program_profiles names)
# ---------------------------------------------------------------------------
_PROGRAM_SYNONYMS = {
    "afm": "accounting and financial management", "cs": "computer science",
    "cfm": "computing and financial management", "se": "software engineering",
    "syde": "systems design engineering", "bme": "biomedical engineering",
    "kin": "kinesiology", "eng": "engineering", "engg": "engineering", "sci": "science",
    "bhsc": "health sciences", "hsci": "health sciences", "medsci": "medical sciences",
    "lifesci": "life sciences", "ibiomed": "integrated biomedical engineering health sciences",
    "math": "mathematics", "maths": "mathematics", "stats": "statistics", "psych": "psychology",
    "econ": "economics", "mgmt": "management", "bba": "business administration",
    "bcom": "commerce", "bscn": "nursing", "bkin": "kinesiology", "bhs": "health studies",
}
_STOP = {
    "and", "of", "the", "in", "with", "bachelor", "bsc", "ba", "bba", "basc", "bcom", "beng",
    "bmath", "bes", "bfa", "bas", "bkin", "bmus", "bsw", "bscn", "bed", "hon", "hons", "honours",
    "honors", "honour", "h", "program", "programs", "degree", "major", "i", "ii", "regular",
    "only", "optional", "available", "stream", "including", "internship", "or", "campus",
    "at", "for", "a", "an", "1", "gateway", "direct", "entry", "year", "years",
    # business/engineering school brand names that applicants add or omit
    "smith", "schulich", "telfer", "lazaridis", "goodman", "degroote", "ivey", "sprott",
    "ted", "rogers", "odette", "lassonde",
}
_NOISE_PARENS = re.compile(
    r"\((?:[^()]*\b(?:years?|immersion|including|options?|available|stream|campus|site|at)\b[^()]*)\)", re.I)
_COOP_RE = re.compile(r"\bco ?op\b")


def program_tokens(name, school=None):
    """(frozenset of core tokens, has_coop) for loose program-name matching.

    Drops degree abbreviations, 'honours', stream words ('regular', 'only'),
    a leading school name, and singularizes simple plurals so that e.g.
    "Life Sciences (Co-op and Regular)" ~ "Life Science Co-op".
    """
    k = key(_NOISE_PARENS.sub(" ", str(name or "")))
    if school:
        prefixes = {key(school)} | {a for a, n in ALIASES.items() if n == school and len(a) > 3}
        for prefix in sorted(prefixes, key=len, reverse=True):
            if k.startswith(prefix + " "):
                k = k[len(prefix) + 1:]
                break
    has_coop = bool(_COOP_RE.search(k))
    k = _COOP_RE.sub(" ", k)
    toks = []
    for t in k.split():
        for u in _PROGRAM_SYNONYMS.get(t, t).split():
            if u in _STOP:
                continue
            if len(u) > 4 and u.endswith("ies"):
                u = u[:-3] + "y"
            elif len(u) > 3 and u.endswith("s") and not u.endswith(("ss", "us", "is")):
                u = u[:-1]
            toks.append(u)
    return frozenset(toks), has_coop


def best_program_match(name, candidates, school=None):
    """Pick the candidate program name that `name` most plausibly refers to, or None.

    Exact core-token match first (the co-op flag breaks ties), then the
    largest candidate whose tokens are all contained in `name` and cover at
    least 75% of its tokens (and is unambiguous).
    """
    toks, coop = program_tokens(name, school)
    if not toks:
        return None
    cands = [(c, *program_tokens(c, school)) for c in candidates]

    def pick(group):
        same_coop = [c for c in group if c[2] == coop]
        return sorted(same_coop or group, key=lambda c: (len(c[0]), c[0]))[0][0]

    exact = [c for c in cands if c[1] == toks]
    if exact:
        return pick(exact)
    subset = [c for c in cands if c[1] and c[1] <= toks and len(c[1]) / len(toks) >= 0.75]
    if subset:
        best = max(len(c[1]) for c in subset)
        top = [c for c in subset if len(c[1]) == best]
        if len({c[1] for c in top}) == 1:
            return pick(top)
    return None
