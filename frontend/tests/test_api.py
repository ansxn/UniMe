"""API tests. Run from frontend/:  python -m pytest tests"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import index  # noqa: E402
from _unime.scoring import compute_matches, enhanced_interest_score  # noqa: E402

CS_ANSWERS = {
    "wa": "5", "wc": "3", "wso": "2", "AA": ["cs-math", "engineering"],
    "LC": ["Mathematics", "Computer Science", "Physics"], "ME": "5", "CR": "4", "CO": "5",
    "UR": "3", "CE": "4", "SET": "Urban", "CPS": "Large", "CSB": "200+",
    "HS": ["Traditional dorm"], "NS": "3", "CLB": ["Hackathons"], "SPT": "varsity", "CEV": "3",
}


@pytest.fixture
def client():
    index.app.config["TESTING"] = True
    return index.app.test_client()


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["ok"] and body["programs"] > 1000 and body["admissions_rows"] > 1000


def test_match_returns_ranked_top_10(client):
    res = client.post("/api/match", json=CS_ANSWERS)
    assert res.status_code == 200
    matches = res.get_json()
    assert len(matches) == 10
    assert [m["overall"] for m in matches] == sorted((m["overall"] for m in matches), reverse=True)
    assert any("Engineering" in m["program"] or "Computer" in m["program"] for m in matches[:3])


def test_programs_are_deduplicated():
    keys = [(p["uni"], p["program"]) for p in index.PROGRAMS]
    assert len(keys) == len(set(keys))
    assert not any("–" in p["uni"] for p in index.PROGRAMS)


def test_sports_answer_affects_social_score():
    # Regression: SPT used to be split into characters, so it never matched anything.
    def program(name, sports):
        return {"uni": name, "program": "X", "academic": {"interests": []},
                "campus": {}, "social": {"sports": sports}}
    progs = [program("Few", ["Soccer"]), program("Many", ["Soccer", "Hockey", "Basketball", "Football"]),
             program("None", [])]

    def social(spt):
        return {m["school"]: m["social"] for m in compute_matches(progs, {**CS_ANSWERS, "SPT": spt})}

    varsity, rec, none = social("varsity"), social("rec"), social("none")
    assert varsity["Many"] > varsity["Few"] > varsity["None"]
    assert rec["Many"] == rec["Few"] > rec["None"]
    assert none["Many"] == none["Few"] == none["None"]


def test_interest_areas_all_match_something():
    # Regression: social-sciences / education-law / undecided matched no programs.
    for area in ("engineering", "cs-math", "business", "health", "sciences",
                 "social-sciences", "arts-humanities", "education-law"):
        best = max(enhanced_interest_score([area], p["academic"]["interests"]) for p in index.PROGRAMS)
        assert best == 1.0, area
    assert enhanced_interest_score(["undecided"], ["Anything"]) == 0.5


def test_education_law_ranks_relevant_programs(client):
    res = client.post("/api/match", json={**CS_ANSWERS, "AA": ["education-law"], "LC": []})
    programs = " ".join(m["program"].lower() for m in res.get_json())
    assert any(w in programs for w in ("education", "law", "justice", "criminology", "policy", "political"))


@pytest.mark.parametrize("bad", [{"ME": "abc"}, {"ME": 9}, {"wa": "x"}, {"AA": 5}])
def test_match_rejects_bad_input_with_400(client, bad):
    res = client.post("/api/match", json={**CS_ANSWERS, **bad})
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_match_zero_weights_does_not_crash(client):
    assert client.post("/api/match", json={**CS_ANSWERS, "wa": 0, "wc": 0, "wso": 0}).status_code == 200


def test_match_rejects_non_object_body(client):
    assert client.post("/api/match", data="nope", content_type="application/json").status_code == 400


def test_report_pdf_uses_answers(client):
    res = client.post("/api/report-pdf", json=CS_ANSWERS)
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF")


@pytest.mark.parametrize("school", ["Waterloo", "University of Waterloo", "uwaterloo"])
def test_chance_me_accepts_school_aliases(client, school):
    res = client.post("/api/chance-me", json={"school": school, "program": "Software Engineering",
                                               "top6": 93, "ecs": "robotics, student council, volunteering"})
    pred = res.get_json()["prediction"]
    assert pred["found"] and pred["school"] == "Waterloo"
    assert 0 < pred["chance"] < 100
    assert pred["sample_size"] > 5


def test_chance_me_unknown_program(client):
    pred = client.post("/api/chance-me", json={"school": "Waterloo", "program": "Underwater Basket Weaving",
                                                "top6": 90}).get_json()["prediction"]
    assert pred == {"found": False, "reason": "program", "message": pred["message"]}


@pytest.mark.parametrize("bad", [{"top6": "abc"}, {"top6": 150}, {"school": ""}])
def test_chance_me_validation(client, bad):
    body = {"school": "Waterloo", "program": "Software Engineering", "top6": 93, **bad}
    assert client.post("/api/chance-me", json=body).status_code == 400


def test_chance_options(client):
    opts = client.get("/api/chance-options").get_json()
    schools = {o["school"] for o in opts}
    assert {"Waterloo", "Western", "McMaster"} <= schools


def test_mentors_for_program_and_fallbacks(client):
    def get(school, program):
        return client.get("/api/program-mentors", query_string={"school": school, "program": program}).get_json()

    western = get("Western University", "Computer Science")
    assert western["match"] == "program"
    assert {m["name"] for m in western["mentors"]} == {"Anson Wang", "Kevin Li"}

    waterloo_other = get("University of Waterloo", "Management Engineering (Co-op Only)")
    assert waterloo_other["match"] == "school"
    assert all(m["school"] == "University of Waterloo" for m in waterloo_other["mentors"])

    assert get("Trent University", "History")["match"] == "general"


def test_mentor_avatars_exist_in_public():
    public = os.path.join(os.path.dirname(__file__), "..", "public")
    for m in index.MENTORS["mentors"]:
        assert m["avatar"].startswith("/"), m["avatar"]
        assert os.path.exists(os.path.join(public, m["avatar"].lstrip("/"))), m["avatar"]


def test_unknown_route_is_json_404(client):
    res = client.get("/api/nope")
    assert res.status_code == 404 and res.get_json()["success"] is False
