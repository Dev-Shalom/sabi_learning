"""The JSON API, driven the way a client drives it.

Most of this file is about exam mode, because exam mode is where the
properties are. Four of them, each with a failure it exists to prevent:

* the server owns the clock, so tampering with the device time does nothing;
* nothing is marked before submission, so a timed sitting is not a guessing
  game against the marker;
* a replayed offline queue cannot overwrite a newer answer with a stale one;
* a submitted sitting is closed, and there is no result before it is.

The other rule running through every read: no endpoint may return a question
that is not `verified`, or whose licence is `dev_only`.
"""

from __future__ import annotations

import re
import uuid

import pytest
from sqlalchemy import select

from sabi.api.v1.deps import CSRF_HEADER
from sabi.content import subjects as subjects_mod
from sabi.models import ExamAnswer, Question, Subject

EMAIL = "api@example.test"
PASSWORD = "the-server-owns-the-clock-2026"


# --------------------------------------------------------------- fixtures


def csrf(client) -> str:
    page = client.get("/app").text
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def headers(client) -> dict:
    return {CSRF_HEADER: csrf(client)}


def sign_up(client, email: str = EMAIL) -> None:
    client.post(
        "/signup",
        data={"email": email, "password": PASSWORD, "csrf_token": csrf(client)},
    )


@pytest.fixture
def bank(session):
    """A small verified question bank, plus one of everything unservable.

    Committed, not just flushed: the API runs on its own session, and rows
    left inside this fixture's open transaction are invisible to it. The
    conftest truncates between tests, so committing here does not leak.
    """
    subjects_mod.sync(session)
    session.commit()

    made = []
    for i in range(1, 13):
        q = Question(
            id=f"waec-2019-chemistry-p1-{i}",
            exam_body="WAEC", subject_code="CHM", year=2019, paper="1",
            question_number=i, type="objective",
            stem=f"Chemistry question {i}?",
            options=[
                {"label": "A", "text": "first", "why_wrong": "A common slip."},
                {"label": "B", "text": "second"},
                {"label": "C", "text": "third"},
                {"label": "D", "text": "fourth"},
            ],
            answer={"key": "B"},
            explanation={"text": f"Because of reason {i}.", "locators": ["CHM B1"]},
            topic="Mole concept", status="verified", licence="original",
            stem_hash=f"h{i}",
        )
        session.add(q)
        made.append(q)

    # One of each kind that must never be served.
    session.add(
        Question(
            id="waec-2019-chemistry-p1-90", exam_body="WAEC", subject_code="CHM",
            year=2019, paper="1", question_number=90, type="objective",
            stem="UNREVIEWED: this must never be shown",
            options=[{"label": "A", "text": "x"}], answer={"key": "A"},
            status="draft", licence="original", stem_hash="h90",
        )
    )
    session.add(
        Question(
            id="waec-2019-chemistry-p1-91", exam_body="WAEC", subject_code="CHM",
            year=2019, paper="1", question_number=91, type="objective",
            stem="DEV ONLY: this must never be shown",
            options=[{"label": "A", "text": "x"}], answer={"key": "A"},
            status="verified", licence="dev_only", stem_hash="h91",
        )
    )
    session.commit()
    subjects_mod.refresh_availability(session, threshold=1)
    session.commit()
    return made


# ------------------------------------------------------------------ viewer


def test_the_viewer_endpoint_works_for_an_anonymous_caller(client):
    """Asking without an account is the default, not a degraded mode."""
    r = client.get("/api/auth/viewer")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is False
    assert body["consent_state"] == "not_required"
    assert body["allowance"]["questions_cap"] > 0


def test_the_viewer_reflects_signing_up(client):
    sign_up(client)
    body = client.get("/api/auth/viewer").json()
    assert body["authenticated"] is True
    assert body["display_name"] == EMAIL
    assert body["onboarded"] is False


# ----------------------------------------------------------------- catalog


def test_only_available_subjects_are_listed(client, bank, session):
    body = client.get("/api/catalog/subjects").json()
    codes = {s["code"] for s in body}
    assert "CHM" in codes
    # Nothing else has content, so nothing else is offered.
    assert codes == {"CHM"}

    everything = client.get("/api/catalog/subjects?include_unavailable=true").json()
    assert len(everything) > len(body)


def test_years_are_never_padded(client, bank):
    chm = next(s for s in client.get("/api/catalog/subjects").json() if s["code"] == "CHM")
    assert chm["years_available"] == [2019], (
        "a year with no servable questions was offered"
    )


def test_the_exam_catalog_carries_the_keyboard_map(client):
    body = client.get("/api/catalog/exams").json()
    jamb = next(f for f in body if f["exam_body"] == "JAMB")
    kb = jamb["keyboard"]
    assert kb["select_option"] == {"A": "a", "B": "b", "C": "c", "D": "d"}
    assert "ArrowRight" in kb["next"]
    assert kb["confirm_submit"] == ["y"] and kb["cancel_submit"] == ["r"]
    assert jamb["option_labels"] == ["A", "B", "C", "D"]


# ---------------------------------------------------------------- practice


def test_a_practice_set_never_contains_an_unservable_question(client, bank):
    sign_up(client)
    r = client.post(
        "/api/practice/sets",
        json={"subject_code": "CHM", "count": 12},
        headers=headers(client),
    )
    assert r.status_code == 201
    stems = [i["question"]["stem"] for i in r.json()["items"]]
    assert stems
    assert not any("UNREVIEWED" in s or "DEV ONLY" in s for s in stems)


def test_a_practice_question_carries_no_answer_key(client, bank):
    """The shape is the safety property: there is no field to leak."""
    sign_up(client)
    r = client.post(
        "/api/practice/sets", json={"subject_code": "CHM", "count": 3},
        headers=headers(client),
    )
    first = r.json()["items"][0]["question"]
    assert set(first) == {
        "id", "type", "stem", "passage", "options", "assets", "topic", "source_label"
    }
    for option in first["options"]:
        assert set(option) == {"label", "text"}, "why_wrong leaked before marking"


def test_practice_marks_immediately_and_explains(client, bank):
    sign_up(client)
    made = client.post(
        "/api/practice/sets", json={"subject_code": "CHM", "count": 5},
        headers=headers(client),
    ).json()
    qid = made["items"][0]["question"]["id"]

    wrong = client.post(
        f"/api/practice/sets/{made['id']}/answer",
        json={"question_id": qid, "selected_label": "A"},
        headers=headers(client),
    ).json()
    assert wrong["correct"] is False
    assert wrong["correct_label"] == "B"
    assert wrong["explanation"]
    assert wrong["why_wrong"] == "A common slip."
    assert wrong["locators"] == ["CHM B1"]

    right = client.post(
        f"/api/practice/sets/{made['id']}/answer",
        json={"question_id": qid, "selected_label": "B"},
        headers=headers(client),
    ).json()
    assert right["correct"] is True


def test_changing_a_practice_answer_updates_rather_than_duplicates(client, bank, session):
    from sabi.models import PracticeResponse

    sign_up(client)
    made = client.post(
        "/api/practice/sets", json={"subject_code": "CHM", "count": 3},
        headers=headers(client),
    ).json()
    qid = made["items"][0]["question"]["id"]
    for label in ("A", "C", "B"):
        client.post(
            f"/api/practice/sets/{made['id']}/answer",
            json={"question_id": qid, "selected_label": label},
            headers=headers(client),
        )
    session.expire_all()
    rows = session.execute(select(PracticeResponse)).scalars().all()
    assert len(rows) == 1
    assert rows[0].given == "B" and rows[0].correct is True


# ---------------------------------------------------------------- exam mode


def _start_exam(client):
    return client.post(
        "/api/exam/sessions",
        json={"format_key": "jamb_utme", "subject_codes": ["CHM"]},
        headers=headers(client),
    )


def test_an_exam_reveals_no_marking_before_submission(client, bank):
    """The property that makes it a mock rather than a quiz."""
    sign_up(client)
    made = _start_exam(client)
    assert made.status_code == 201, made.text
    body = made.json()

    assert body["state"] == "active"
    assert body["items"], "an exam with no questions"
    assert all(i["marking"] is None for i in body["items"])
    assert body["score"] is None

    qid = body["items"][0]["question"]["id"]
    saved = client.post(
        f"/api/exam/sessions/{body['id']}/answers",
        json=[{"question_id": qid, "selected_label": "B", "client_seq": 1}],
        headers=headers(client),
    )
    assert saved.status_code == 200
    # The autosave response deliberately carries no items and no marking.
    assert saved.json()["items"] == []
    assert saved.json()["answered_count"] == 1

    still = client.get(f"/api/exam/sessions/{body['id']}").json()
    assert all(i["marking"] is None for i in still["items"])


def test_the_result_is_refused_until_the_exam_is_submitted(client, bank):
    sign_up(client)
    body = _start_exam(client).json()
    r = client.get(f"/api/exam/sessions/{body['id']}/result")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "conflict"


def test_submitting_marks_and_scores_in_the_exams_own_scale(client, bank):
    sign_up(client)
    body = _start_exam(client).json()
    ids = [i["question"]["id"] for i in body["items"]]

    # Answer them all correctly; every seeded question keys to B.
    client.post(
        f"/api/exam/sessions/{body['id']}/answers",
        json=[
            {"question_id": q, "selected_label": "B", "client_seq": 1} for q in ids
        ],
        headers=headers(client),
    )
    done = client.post(
        f"/api/exam/sessions/{body['id']}/submit", headers=headers(client)
    ).json()

    assert done["state"] == "submitted"
    assert done["scale_max"] == 400, "scored on something other than the UTME scale"
    assert done["score"] == 400
    assert all(i["marking"]["correct"] for i in done["items"])

    result = client.get(f"/api/exam/sessions/{body['id']}/result").json()
    assert result["correct"] == result["total"] == len(ids)
    assert result["scale_max"] == 400
    assert result["sections"]


def test_a_submitted_exam_accepts_no_more_answers(client, bank):
    """Otherwise the answers are revealed and then the score can be raised."""
    sign_up(client)
    body = _start_exam(client).json()
    qid = body["items"][0]["question"]["id"]

    client.post(
        f"/api/exam/sessions/{body['id']}/answers",
        json=[{"question_id": qid, "selected_label": "A", "client_seq": 1}],
        headers=headers(client),
    )
    client.post(f"/api/exam/sessions/{body['id']}/submit", headers=headers(client))

    late = client.post(
        f"/api/exam/sessions/{body['id']}/answers",
        json=[{"question_id": qid, "selected_label": "B", "client_seq": 2}],
        headers=headers(client),
    )
    assert late.status_code == 409


def test_submitting_twice_returns_the_result_rather_than_an_error(client, bank):
    """A student whose connection dropped mid-submit will press it again."""
    sign_up(client)
    body = _start_exam(client).json()
    first = client.post(
        f"/api/exam/sessions/{body['id']}/submit", headers=headers(client)
    )
    second = client.post(
        f"/api/exam/sessions/{body['id']}/submit", headers=headers(client)
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["score"] == second.json()["score"]


def test_a_stale_queued_answer_cannot_overwrite_a_newer_one(client, bank, session):
    """The reason `client_seq` exists.

    An offline client replays its queue on reconnection and it can arrive out
    of order. Last-write-wins would let the stale entry win and the student
    would never know their correction was lost.
    """
    sign_up(client)
    body = _start_exam(client).json()
    qid = body["items"][0]["question"]["id"]
    sid = body["id"]

    # The newer answer arrives first, as it would if it were made online while
    # an older one was still sitting in the offline queue.
    client.post(
        f"/api/exam/sessions/{sid}/answers",
        json=[{"question_id": qid, "selected_label": "B", "client_seq": 7}],
        headers=headers(client),
    )
    # Then the queue flushes an older one.
    client.post(
        f"/api/exam/sessions/{sid}/answers",
        json=[{"question_id": qid, "selected_label": "A", "client_seq": 3}],
        headers=headers(client),
    )

    current = client.get(f"/api/exam/sessions/{sid}").json()
    answer = next(i for i in current["items"] if i["question"]["id"] == qid)
    assert answer["selected_label"] == "B", (
        "a stale queued answer overwrote a newer one"
    )


def test_replaying_the_same_sequence_is_idempotent(client, bank):
    sign_up(client)
    body = _start_exam(client).json()
    qid = body["items"][0]["question"]["id"]
    payload = [{"question_id": qid, "selected_label": "C", "client_seq": 4}]
    for _ in range(3):
        client.post(
            f"/api/exam/sessions/{body['id']}/answers",
            json=payload,
            headers=headers(client),
        )
    current = client.get(f"/api/exam/sessions/{body['id']}").json()
    assert current["answered_count"] == 1


def test_an_answer_for_a_question_not_in_the_sitting_is_ignored_not_fatal(client, bank):
    """One bad entry in a replayed queue must not discard the rest of it."""
    sign_up(client)
    body = _start_exam(client).json()
    good = body["items"][0]["question"]["id"]

    r = client.post(
        f"/api/exam/sessions/{body['id']}/answers",
        json=[
            {"question_id": "not-in-this-exam", "selected_label": "A", "client_seq": 1},
            {"question_id": good, "selected_label": "B", "client_seq": 1},
        ],
        headers=headers(client),
    )
    assert r.status_code == 200
    assert r.json()["answered_count"] == 1


def test_the_clock_comes_from_the_server(client, bank):
    """The client displays `seconds_remaining`; it never computes it."""
    sign_up(client)
    body = _start_exam(client).json()
    assert 0 < body["seconds_remaining"] <= 120 * 60
    again = client.get(f"/api/exam/sessions/{body['id']}").json()
    assert again["seconds_remaining"] <= body["seconds_remaining"]


def test_an_exam_session_belongs_to_one_student(client, bank):
    from conftest import FormClient

    from sabi.api.app import app

    sign_up(client)
    body = _start_exam(client).json()

    stranger = FormClient(app)
    stranger.get("/app")
    sign_up(stranger, email="stranger-api@example.test")

    # Same answer for "not yours" as for "does not exist", so an id cannot be
    # probed for existence.
    assert stranger.get(f"/api/exam/sessions/{body['id']}").status_code == 404
    assert (
        stranger.post(
            f"/api/exam/sessions/{body['id']}/submit", headers=headers(stranger)
        ).status_code
        == 404
    )


def test_the_daily_exam_cap_is_enforced(client, bank, session):
    from sabi.limits import limiter
    from sabi.models import Plan

    sign_up(client)
    plan = limiter.plan_for(session, _user(session))
    session.execute(
        Plan.__table__.update().where(Plan.name == plan.name).values(daily_exam_cap=1)
    )
    session.commit()

    assert _start_exam(client).status_code == 201
    second = _start_exam(client)
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "rate_limited"


# ------------------------------------------------------------------ access


def test_exam_mode_needs_an_account(client, bank):
    r = client.post(
        "/api/exam/sessions",
        json={"format_key": "jamb_utme", "subject_codes": ["CHM"]},
        headers=headers(client),
    )
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "unauthenticated"


def test_a_mutating_request_without_a_token_is_refused(client, bank):
    """Every state-changing request carries CSRF protection."""
    sign_up(client)
    r = client.post(
        "/api/practice/sets", json={"subject_code": "CHM", "count": 3}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "forbidden"


def test_every_mutating_api_route_depends_on_a_csrf_guard():
    """Enumerated, so a new route cannot quietly ship without one.

    The Jinja surface shipped four routes with a login check and no token
    check, and the difference is invisible from the outside. This is the same
    guard for the API.
    """
    from sabi.api.app import app

    guards = {"require_csrf_header", "require_account_csrf"}
    missing = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if not path.startswith("/api"):
            continue
        if not (methods & {"POST", "PUT", "PATCH", "DELETE"}):
            continue
        names = {
            d.call.__name__
            for d in getattr(route, "dependant", None).dependencies
            if getattr(d, "call", None)
        }
        # A guard may be reached through another guard, so walk one level.
        nested = set()
        for d in getattr(route, "dependant", None).dependencies:
            for sub in getattr(d, "dependencies", []):
                if getattr(sub, "call", None):
                    nested.add(sub.call.__name__)
        if not ((names | nested) & guards):
            missing.append(f"{sorted(methods - {'HEAD'})} {path}")

    assert not missing, f"mutating API routes with no CSRF guard: {missing}"


# ----------------------------------------------------------------- reading


def test_reading_never_returns_an_unservable_question(client, bank):
    body = client.get("/api/reading/questions?subject_code=CHM").json()
    stems = [i["question"]["stem"] for i in body["items"]]
    assert stems
    assert not any("UNREVIEWED" in s or "DEV ONLY" in s for s in stems)
    # Reading shows the answer -- that is the mode -- but only for servable ones.
    assert all(i["answer"]["label"] == "B" for i in body["items"])


def test_reading_is_paginated_and_capped(client, bank):
    first = client.get("/api/reading/questions?subject_code=CHM&limit=5").json()
    assert len(first["items"]) == 5
    assert first["next_cursor"]

    second = client.get(
        f"/api/reading/questions?subject_code=CHM&limit=5&cursor={first['next_cursor']}"
    ).json()
    firsts = {i["question"]["id"] for i in first["items"]}
    seconds = {i["question"]["id"] for i in second["items"]}
    assert not (firsts & seconds), "pagination returned the same question twice"

    over = client.get("/api/reading/questions?subject_code=CHM&limit=500")
    assert over.status_code == 422, "the page cap can be argued past"


# -------------------------------------------------------------- onboarding


def test_onboarding_round_trips(client, bank):
    sign_up(client)
    r = client.put(
        "/api/onboarding",
        json={
            "school_class": "SS3",
            "track": "science",
            "subjects": {"WAEC": ["CHM"]},
            "target": "All credits",
            "daily_minutes": 30,
        },
        headers=headers(client),
    )
    assert r.status_code == 200, r.text
    assert r.json()["completed"] is True

    again = client.get("/api/onboarding").json()
    assert again["school_class"] == "SS3"
    assert again["subjects"] == {"WAEC": ["CHM"]}
    assert client.get("/api/auth/viewer").json()["onboarded"] is True


def test_a_broken_combination_rule_is_explained(client, bank):
    """Named, not silently rejected: a student who cannot see the rule cannot
    fix their choice."""
    sign_up(client)
    r = client.put(
        "/api/onboarding",
        json={"school_class": "SS3", "track": "science", "subjects": {"JAMB": ["CHM"]}},
        headers=headers(client),
    )
    assert r.status_code == 422
    message = r.json()["detail"]["message"]
    assert "JAMB" in message and "4" in message


def test_an_unknown_subject_is_named_back(client, bank):
    sign_up(client)
    r = client.put(
        "/api/onboarding",
        json={"school_class": "SS3", "track": "science",
              "subjects": {"WAEC": ["ZZZ"]}},
        headers=headers(client),
    )
    assert r.status_code == 422
    assert "ZZZ" in r.json()["detail"]["message"]


def _user(session):
    from sabi.models import User

    return session.execute(
        select(User).where(User.email_normalised.is_not(None))
    ).scalars().first()


# ------------------------------------------------- the contract, kept honest


def test_the_published_openapi_is_current():
    """The generated document must match what the server actually serves.

    `web/lib/api-types.ts` is generated from it, so a stale file types the
    front end against an API that no longer exists -- and the failure surfaces
    as a runtime 404 rather than a typecheck error, which is exactly backwards
    from why the types exist.
    """
    import json
    from pathlib import Path

    from sabi.api.app import app

    published = json.loads(
        (Path(__file__).resolve().parent.parent / "contracts" / "openapi.generated.json")
        .read_text(encoding="utf-8")
    )
    live = {
        path: item
        for path, item in app.openapi()["paths"].items()
        if path.startswith("/api")
    }
    assert set(published["paths"]) == set(live), (
        "contracts/openapi.generated.json is stale. Run "
        "`python tools/publish_openapi.py` and regenerate web/lib/api-types.ts."
    )


def test_the_published_document_carries_no_html_routes():
    """Typing an HTML route tells the front end it can fetch JSON from it."""
    import json
    from pathlib import Path

    published = json.loads(
        (Path(__file__).resolve().parent.parent / "contracts" / "openapi.generated.json")
        .read_text(encoding="utf-8")
    )
    stray = [p for p in published["paths"] if not p.startswith("/api")]
    assert not stray, f"non-API paths published: {stray}"


def test_every_promised_path_is_either_served_or_named_as_pending():
    """A path in the contract the server does not serve is a broken promise."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "publish_openapi.py"), "--check"],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
