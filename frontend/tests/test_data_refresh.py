"""Tests for the 2026-11 data refresh: multi-cycle admissions, canonical names,
program facts / trait provenance, recency weighting and official-range fallback.
Run from frontend/:  python -m pytest tests"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import index  # noqa: E402
from _unime import chance, schools  # noqa: E402

ORIGINAL_PREDICTION_FIELDS = {
    "found", "school", "program", "matched_programs", "sample_size", "low_confidence",
    "supp_required", "user_average", "ec_bonus", "adjusted_average", "offer_average",
    "offer_min", "offer_max", "chance", "verdict",
}


@pytest.fixture
def client():
    index.app.config["TESTING"] = True
    return index.app.test_client()


# --------------------------------------------------------------------------- data
def test_admissions_span_multiple_cycles():
    years = {r["year"] for r in index.ADMISSIONS}
    assert len(years) >= 3 and max(years) >= 2025
    assert all(isinstance(r["avg"], float) and 60 <= r["avg"] <= 100 for r in index.ADMISSIONS)


def test_health_reports_admission_years(client):
    body = client.get("/api/health").get_json()
    assert body["admissions_years"] == sorted(body["admissions_years"]) and len(body["admissions_years"]) >= 3


def test_school_names_are_canonical_everywhere():
    canonical = set(schools.CANONICAL)
    assert {p["uni"] for p in index.PROGRAMS} <= canonical
    assert {r["University"] for r in index.ADMISSIONS} <= canonical


def test_no_program_has_empty_campus_or_social():
    assert not [p for p in index.PROGRAMS if not p.get("campus") or not p.get("social")]


def test_programs_record_facts_and_trait_provenance():
    for p in index.PROGRAMS:
        assert {"academic", "campus", "social"} <= set(p["trait_source"])
        assert {"coop_available", "admission_range", "prerequisites", "degree", "city", "source_url"} <= set(p["facts"])
    filled = [p for p in index.PROGRAMS if p["trait_source"]["campus"].startswith("university_table")]
    assert len(filled) >= 150
    tmu = next(p for p in index.PROGRAMS if p["uni"] == "Toronto Metropolitan University")
    assert tmu["facts"]["city"] == "Toronto" and tmu["campus"]["setting"] == "Urban"
    sde = next(p for p in index.PROGRAMS if p["program"] == "Systems Design Engineering (Co-op Only)")
    assert sde["facts"]["coop_available"] is True and sde["facts"]["coop_required"] is True


def test_mentor_keys_exist_in_program_profiles():
    keys = {f"{p['uni']}_{p['program']}" for p in index.PROGRAMS}
    for k in index.MENTORS["programMentors"]:
        assert k in keys, k


# --------------------------------------------------------------------------- aliases
@pytest.mark.parametrize("raw,expected", [
    ("University of Waterloo", "University of Waterloo"), ("Waterloo", "University of Waterloo"),
    ("UofT - SG", "University of Toronto"), ("UTSc", "University of Toronto Scarborough"),
    ("Queen's", "Queen's University"), ("Ryerson", "Toronto Metropolitan University"),
    ("Toronto Metropolitan University (formerly Ryerson University)", "Toronto Metropolitan University"),
    ("Western - Huron", "Western University - Huron University College"),
])
def test_school_aliases(raw, expected):
    assert chance.SCHOOL_ALIASES[schools.key(raw)] == expected
    assert schools.canonical(raw) == expected


def test_uoft_campus_split_by_program_text():
    assert schools.canonical("University of Toronto", "Computer Science - UTM") == "University of Toronto Mississauga"
    assert schools.canonical("University of Toronto", "Life Sciences") == "University of Toronto"


def test_program_matching():
    cands = ["Life Sciences (Regular/Co-op)", "Mathematics (Regular/Co-op)", "Engineering I", "Engineering Co-op I"]
    assert schools.best_program_match("Life Science Co-op", cands) == "Life Sciences (Regular/Co-op)"
    assert schools.best_program_match("Honours Mathematics", cands) == "Mathematics (Regular/Co-op)"
    assert schools.best_program_match("Engineering 1 (Co-op)", cands) == "Engineering Co-op I"
    assert schools.best_program_match("Engineering I", cands) == "Engineering I"
    assert schools.best_program_match("Underwater Basket Weaving", cands) is None


# --------------------------------------------------------------------------- ChanceMe
def test_prediction_keeps_every_original_field(client):
    pred = client.post("/api/chance-me", json={"school": "University of Waterloo", "program": "Software Engineering",
                                               "top6": 95}).get_json()["prediction"]
    assert ORIGINAL_PREDICTION_FIELDS <= set(pred)
    assert pred["basis"] in ("crowd", "blended", "official")
    assert sum(pred["offers_by_year"].values()) == pred["sample_size"]


def _row(school, program, avg, year):
    return {"University": school, "Program name": program, "Decision": "Offer", "avg": float(avg), "year": year,
            "Supp App?": "", "Notable info from supp app": "", "Comments": ""}


def _profile(school, program, low, high):
    return {"uni": school, "program": program,
            "facts": {"admission_range": {"text": f"{low}-{high}%", "low": low, "high": high},
                      "source_url": "https://example.org/program"}}


def test_recent_cycles_weigh_more():
    rows = [_row("U", "Program", 80, 2023)] * 10 + [_row("U", "Program", 95, 2025)] * 10
    pred = chance.predict_admission_chance(rows, "U", "Program", 90)
    assert pred["basis"] == "crowd"
    assert pred["offer_average"] > 87.5  # unweighted mean would be 87.5
    assert pred["sample_size"] == 20 and pred["offers_by_year"] == {"2023": 10, "2025": 10}


def test_official_range_used_when_no_crowd_offers():
    programs = [_profile("U", "Rare Program", 85, 90)]
    rows = [_row("U", "Other", 90, 2025)] * 3
    pred = chance.predict_admission_chance(rows, "U", "Rare Program", 88, programs=programs)
    assert pred["found"] and pred["basis"] == "official"
    assert (pred["offer_min"], pred["offer_average"], pred["offer_max"]) == (85.0, 87.5, 90.0)
    assert pred["sample_size"] == 0 and pred["low_confidence"]
    assert pred["official_range"]["source_url"] == "https://example.org/program"
    assert ORIGINAL_PREDICTION_FIELDS <= set(pred)


def test_official_range_blended_when_few_offers():
    programs = [_profile("U", "Program", 80, 84)]
    rows = [_row("U", "Program", 96, 2025), _row("U", "Program", 96, 2025)]
    pred = chance.predict_admission_chance(rows, "U", "Program", 90, programs=programs)
    assert pred["basis"] == "blended"
    assert 82 < pred["offer_average"] < 96  # pulled between official midpoint and crowd mean


def test_crowd_only_when_enough_offers_even_with_official_range():
    programs = [_profile("U", "Program", 80, 84)]
    rows = [_row("U", "Program", 95, 2025)] * 6
    pred = chance.predict_admission_chance(rows, "U", "Program", 90, programs=programs)
    assert pred["basis"] == "crowd" and pred["offer_average"] == 95.0


def test_unknown_program_shape_unchanged_with_programs():
    pred = chance.predict_admission_chance(index.ADMISSIONS, "Waterloo", "Underwater Basket Weaving", 90,
                                           programs=index.PROGRAMS)
    assert set(pred) == {"found", "reason", "message"} and pred["reason"] == "program"


def test_admissions_csv_has_no_personal_columns():
    path = os.path.join(index.DATA_DIR, "admissionsData.csv")
    with open(path, encoding="utf-8") as f:
        header = f.readline().lower()
    for word in ("timestamp", "reddit", "discord", "username", "citizenship"):
        assert word not in header


def test_profiles_json_is_reasonably_small():
    assert os.path.getsize(os.path.join(index.DATA_DIR, "program_profiles.json")) < 5_000_000
    with open(os.path.join(index.DATA_DIR, "program_profiles.json"), encoding="utf-8") as f:
        assert isinstance(json.load(f), list)
