"""UniMe API (Flask).

On Vercel this file is deployed as a Python function, and next.config.ts
rewrites /api/* to it. Locally, run `npm run dev` (starts Next.js and this
server together) or `python api/index.py` on its own.
"""
import datetime
import json
import os
import random
import sys

from flask import Flask, jsonify, request, send_file

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _unime.chance import chance_options, load_admissions, predict_admission_chance  # noqa: E402
from _unime.pdf_report import generate_matches_pdf_bytes  # noqa: E402
from _unime.scoring import InvalidAnswer, compute_matches, load_programs  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_unime", "data")

app = Flask(__name__)

PROGRAMS = load_programs(os.path.join(DATA_DIR, "program_profiles.json"))
ADMISSIONS = load_admissions(os.path.join(DATA_DIR, "admissionsData.csv"))
with open(os.path.join(DATA_DIR, "mentors.json"), encoding="utf-8") as f:
    MENTORS = json.load(f)


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise InvalidAnswer("Request body must be a JSON object")
    return data


@app.errorhandler(InvalidAnswer)
def _bad_request(e):
    return jsonify({"success": False, "error": str(e)}), 400


@app.errorhandler(Exception)
def _server_error(e):
    code = getattr(e, "code", 500)
    if not isinstance(code, int) or code >= 500:
        app.logger.exception("Unhandled error")
        return jsonify({"success": False, "error": "Something went wrong on our end."}), 500
    return jsonify({"success": False, "error": getattr(e, "description", str(e))}), code


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "programs": len(PROGRAMS), "admissions_rows": len(ADMISSIONS)})


@app.post("/api/match")
def match_api():
    return jsonify(compute_matches(PROGRAMS, _json_body(), num_results=10))


@app.post("/api/report-pdf")
def report_pdf():
    answers = _json_body()
    matches = compute_matches(PROGRAMS, answers, num_results=100)
    weights = {k: answers.get(k, 1) for k in ("wa", "wc", "wso")}
    pdf = generate_matches_pdf_bytes(matches, weights)
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"UniMe_matches_{datetime.date.today().isoformat()}.pdf",
    )


@app.get("/api/chance-options")
def chance_options_api():
    return jsonify(chance_options(ADMISSIONS))


@app.post("/api/chance-me")
def chance_me_api():
    data = _json_body()
    school = str(data.get("school", "")).strip()
    program = str(data.get("program", "")).strip()
    if not school or not program:
        raise InvalidAnswer("School and program are required")
    try:
        top6 = float(data.get("top6"))
    except (TypeError, ValueError):
        raise InvalidAnswer("Top 6 average must be a number")
    if not 0 <= top6 <= 100:
        raise InvalidAnswer("Top 6 average must be between 0 and 100")

    ecs_raw = data.get("ecs", "")
    ecs = ecs_raw if isinstance(ecs_raw, list) else str(ecs_raw).split(",")
    ecs = [str(ec).strip() for ec in ecs if str(ec).strip()]

    result = predict_admission_chance(ADMISSIONS, school, program, top6, ecs)
    return jsonify({"success": True, "prediction": result})


def _norm(s):
    return " ".join(str(s).lower().replace("–", "-").split())


@app.get("/api/program-mentors")
def program_mentors():
    """Mentors for a program: exact program first, then same school, then general."""
    school = _norm(request.args.get("school", ""))
    program = _norm(request.args.get("program", ""))
    mentors = MENTORS.get("mentors", [])

    ids = MENTORS.get("programMentors", {}).get(f"{request.args.get('school', '')}_{request.args.get('program', '')}", [])
    exact = [m for m in mentors if m["id"] in ids] or [
        m for m in mentors if _norm(m["school"]) == school and _norm(m["program"]) in program
    ]
    if exact:
        return jsonify({"match": "program", "mentors": exact})

    same_school = [m for m in mentors if _norm(m["school"]) == school]
    if same_school:
        return jsonify({"match": "school", "mentors": same_school[:2]})

    return jsonify({"match": "general", "mentors": random.sample(mentors, min(2, len(mentors)))})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
