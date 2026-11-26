"""Offline tests for the pipeline's parsers and derivation rules.

Run from data-pipeline/:  python -m pytest tests -q
(No network: build_programs.build() is called with skip_probe and a temp CSV,
and writes to a temp file instead of the real output.)
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import build_admissions as ba  # noqa: E402
import build_programs as bp  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    ("93", 93.0), ("93.5%", 93.5), ("~94", 94.0), ("94 (top 6)", 94.0), ("93,5", 93.5),
    ("92-93", 92.5), ("94ish", 94.0), ("95 gr 12 midterm", 95.0), ("Top 5: 97.4, Top 6: 97.8", 97.8),
    ("low 90s", 92.0), ("Mid 80s", 85.0), ("High 80's", 88.0),
    ("3.5 GPA", None), ("36 R-score (CEGEP)", None), ("90, 91, 92, 97", None), ("56", None),
    ("97.8; IB 41/45", None), ("75-85%", None), ("", None), ("idk", None),
])
def test_parse_average(raw, expected):
    assert ba.parse_average(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Accepted", "Offer"), ("accepted (conditional)", "Offer"), ("Offer", "Offer"),
    ("Rejected", "Rejected"), ("Deferred to Life Sci", "Deferred"), ("Waitlisted", "Waitlisted"), ("", None),
])
def test_normalize_decision(raw, expected):
    assert ba.normalize_decision(raw) == expected


def test_clean_note_drops_handles_and_empties():
    assert ba.clean_note("n/a") == ""
    assert "@" not in ba.clean_note("robotics captain @someone")


def test_clean_program_strips_school_prefix_and_uoft_campus():
    assert ba.clean_program("McMaster University - Health Sciences", "McMaster University") == "Health Sciences"
    assert ba.clean_program("Computer Science - St. George", "University of Toronto") == "Computer Science"


def test_read_generic_skips_out_of_province_and_usernames():
    text = ("Timestamp,What program did you apply to?,What university did you apply to?,"
            "\"Were you accepted, rejected, waitlisted or deferred?\",Acceptance Average,"
            "Mention any notable extra curricular activities,Province/State/Territory of Residence,Reddit username\n"
            "1/1/2024,Computer Science,University of Waterloo,Accepted,95,robotics,Ontario,someone\n"
            "1/1/2024,Computer Science,University of Waterloo,Accepted,95,,Alberta,other\n")
    rows = ba.read_generic(text)
    assert [r["ontario"] for r in rows] == [True, False]
    assert all("someone" not in json.dumps(r) for r in rows)


@pytest.mark.parametrize("text,low,high", [
    ("Low 90s", 90, 93), ("Mid-to-high 80s", 83, 90), ("85-90%", 85, 90), ("80%+", 80, None), ("75%", 75, 75),
])
def test_parse_admission_range(text, low, high):
    r = bp.parse_admission_range(text)
    assert (r["low"], r["high"]) == (low, high)


def test_coop_from_name():
    assert bp.coop_from_name("Software Engineering (Co-op Only)") == "only"
    assert bp.coop_from_name("Computer Science (Regular/Co-op)") == "available"
    assert bp.coop_from_name("History") is None


def test_math_from_prereqs():
    assert bp.math_from_prereqs(["ENG4U", "MCV4U"]) == 5
    assert bp.math_from_prereqs(["ENG4U", "MHF4U"]) == 4
    assert bp.math_from_prereqs(["ENG4U"]) == 2
    assert bp.math_from_prereqs(None) is None


def test_derive_academic_uses_similar_program_then_facts():
    ref = [{"program": "Computer Science", "academic": {**{t: 4 for t in bp.TRAITS}, "interests": ["Programming"],
                                                         "liked_hs_courses": ["Mathematics"], "alt_to_engineering": []}}]
    acad, src = bp.derive_academic("Computer Science (BSc)", {"coop": "none", "prerequisites": ["MCV4U", "ICS4U"]}, ref)
    assert src == "derived:similar_program"
    assert acad["coop_importance"] == 2 and acad["math_enjoyment"] == 5 and acad["learning_style"] == 4
    assert "Computer Science" in acad["liked_hs_courses"]

    acad, src = bp.derive_academic("Nursing", {"coop": None, "prerequisites": None}, [])
    assert src == "derived:heuristic" and acad["career_certainty"] == 5


def test_build_programs_merges_and_adds_official_rows(tmp_path, monkeypatch):
    csv_path = tmp_path / "official.csv"
    csv_path.write_text(
        "uni,program,campus,degree,coop,prerequisites,admission_range,source_url,retrieved\n"
        "University of Waterloo,Systems Design Engineering (Co-op Only),Waterloo,BASc,only,MCV4U;SPH4U,Low 90s,https://x/syde,2026-11-25\n"
        "Waterloo,Brand New Data Science,Waterloo,BSc,available,MCV4U,Mid 80s,https://x/new,2026-11-25\n",
        encoding="utf-8")
    monkeypatch.setattr(bp, "OUT", str(tmp_path / "out.json"))
    programs, stats = bp.build(skip_probe=True, log=lambda *a: None, official_path=str(csv_path))
    assert stats["official_merged"] == 1 and stats["official_added"] == 1 and stats["empty_campus_after"] == 0
    syde = next(p for p in programs if p["program"] == "Systems Design Engineering (Co-op Only)")
    assert syde["trait_source"]["academic"] == "carried_over"
    assert syde["facts"]["admission_range"]["low"] == 90 and syde["facts"]["source_url"] == "https://x/syde"
    new = next(p for p in programs if p["program"] == "Brand New Data Science")
    assert new["trait_source"]["academic"].startswith("derived:")
    assert new["trait_source"]["campus"].startswith("university_table")
    assert new["academic"]["coop_importance"] == 4 and new["academic"]["math_enjoyment"] == 5
