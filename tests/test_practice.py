"""Practice: the rules that make a score mean something.

The arithmetic is verified in `test_practice_templates.py`, which recomputes
every template's answer independently. This file covers the rest -- who may
answer what, when a mark becomes visible, and whether a student can improve
a score they have already seen.

The three that matter most:

* An answer cannot be changed after the set is closed, or the score is just
  a measure of how long somebody kept typing.
* No mark is visible before the set is closed, or a timed set becomes a
  guessing game against the marker.
* A set belongs to one student, and an id alone is not enough to reach it.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from sabi import practice
from sabi.models import PracticeItem, PracticeResponse, PracticeSet
from sabi.practice import templates as templates_mod

EMAIL = "sitter@example.test"
PASSWORD = "sum-of-interior-angles-2026"


def csrf(client, path="/app"):
    return re.search(
        r'name="csrf_token" value="([^"]+)"', client.get(path).text
    ).group(1)


def sign_up(client, email=EMAIL):
    return client.post(
        "/signup",
        data={"email": email, "password": PASSWORD, "csrf_token": csrf(client, "/signup")},
    )


def start(client, subject="Mathematics", topic=""):
    r = client.post(
        "/practice/start",
        data={"subject": subject, "topic": topic, "csrf_token": csrf(client, "/practice")},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:400]
    return r.headers["location"]


def items_on(client, url):
    return re.findall(r'name="item_id" value="(\d+)"', client.get(url).text)


def answers_for(session, set_id):
    rows = session.execute(
        select(PracticeItem).where(PracticeItem.set_id == set_id).order_by(PracticeItem.position)
    ).scalars().all()
    return {str(r.id): r.answer for r in rows}


# ------------------------------------------------------------------ the point


def test_no_mark_is_visible_until_the_set_is_finished(client, session):
    """A timed set that marks as you type is a guessing game, not practice."""
    sign_up(client)
    url = start(client)
    set_id = int(url.rsplit("/", 1)[1])
    answers = answers_for(session, set_id)

    first = items_on(client, url)[0]
    client.post(
        f"{url}/answer",
        data={"item_id": first, "given": answers[first], "csrf_token": csrf(client, url)},
    )

    page = client.get(url).text
    assert "practice-verdict" not in page, "a mark appeared before the set was closed"
    assert "is-right" not in page and "is-wrong" not in page
    # The typed answer is still shown, so the student can see what they put.
    assert answers[first] in page

    client.post(f"{url}/finish", data={"csrf_token": csrf(client, url)})
    done = client.get(url).text
    assert "practice-verdict" in done
    assert "is-right" in done


def test_a_closed_set_stops_accepting_answers(client, session):
    """Otherwise the answers are shown and then the score can be raised."""
    sign_up(client)
    url = start(client)
    set_id = int(url.rsplit("/", 1)[1])
    answers = answers_for(session, set_id)
    ids = items_on(client, url)

    # Answer one wrongly, close, then try to correct it.
    client.post(
        f"{url}/answer",
        data={"item_id": ids[0], "given": "definitely-wrong", "csrf_token": csrf(client, url)},
    )
    client.post(f"{url}/finish", data={"csrf_token": csrf(client, url)})

    late = client.post(
        f"{url}/answer",
        data={"item_id": ids[0], "given": answers[ids[0]], "csrf_token": csrf(client, url)},
    )
    assert late.status_code == 404

    session.expire_all()
    row = session.execute(
        select(PracticeResponse).where(PracticeResponse.item_id == int(ids[0]))
    ).scalar_one()
    assert row.given == "definitely-wrong"
    assert row.correct is False


def test_changing_an_answer_updates_rather_than_duplicates(client, session):
    """Two rows for one question would let a student average themselves up."""
    sign_up(client)
    url = start(client)
    ids = items_on(client, url)

    for attempt in ("first", "second", "third"):
        client.post(
            f"{url}/answer",
            data={"item_id": ids[0], "given": attempt, "csrf_token": csrf(client, url)},
        )

    session.expire_all()
    rows = session.execute(
        select(PracticeResponse).where(PracticeResponse.item_id == int(ids[0]))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].given == "third"


def test_a_set_belongs_to_one_student(client, session):
    from conftest import FormClient

    from sabi.api.app import app

    sign_up(client)
    url = start(client)
    ids = items_on(client, url)

    stranger = FormClient(app)
    stranger.get("/app")
    sign_up(stranger, email="stranger-sitter@example.test")

    assert stranger.get(url).status_code == 404, "a stranger read somebody else's set"

    r = stranger.post(
        f"{url}/answer",
        data={"item_id": ids[0], "given": "1", "csrf_token": csrf(stranger)},
    )
    assert r.status_code == 404

    r = stranger.post(f"{url}/finish", data={"csrf_token": csrf(stranger)})
    assert r.status_code == 404

    session.expire_all()
    assert session.get(PracticeSet, int(url.rsplit("/", 1)[1])).finished_at is None


def test_practice_is_behind_a_login(client):
    """An anonymous score would vanish with the browser, taking the point with it."""
    for path in ("/practice", "/practice/1"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]


# ------------------------------------------------------------------ the marking


def test_the_marker_accepts_how_a_student_actually_writes_it(client, session):
    """Right answer, wrong formatting, is still a right answer."""
    sign_up(client)
    url = start(client, topic="Polygons")
    set_id = int(url.rsplit("/", 1)[1])

    rows = session.execute(
        select(PracticeItem).where(PracticeItem.set_id == set_id)
    ).scalars().all()
    # Polygon answers are whole degrees, so a student may add the unit or a
    # thousands separator and must not be marked down for it.
    target = next(r for r in rows if r.answer.isdigit() and len(r.answer) >= 4)
    dressed = f"{int(target.answer):,} degrees"

    client.post(
        f"{url}/answer",
        data={"item_id": target.id, "given": dressed, "csrf_token": csrf(client, url)},
    )
    session.expire_all()
    row = session.execute(
        select(PracticeResponse).where(PracticeResponse.item_id == target.id)
    ).scalar_one()
    assert row.correct is True, f"{dressed!r} was not accepted for {target.answer!r}"


def test_an_unanswered_question_counts_as_wrong_not_as_missing(client, session):
    sign_up(client)
    url = start(client)
    client.post(f"{url}/finish", data={"csrf_token": csrf(client, url)})

    done = client.get(url).text
    assert "You did not answer this one" in done
    assert "You scored <strong>0</strong>" in done


# -------------------------------------------------------------- weak topics


def test_a_topic_is_only_weak_once_there_is_evidence(client, session):
    """One bad morning should not rewrite a student's dashboard."""
    sign_up(client)
    url = start(client)
    ids = items_on(client, url)

    # Two wrong answers is not enough to call anything weak.
    for item_id in ids[:2]:
        client.post(
            f"{url}/answer",
            data={"item_id": item_id, "given": "0", "csrf_token": csrf(client, url)},
        )

    session.expire_all()
    user = _user(session)
    assert practice.weak_subtopics(session, user=user) == []

    rates = practice.topic_rates(session, user=user)
    assert rates, "answers were recorded but no topic rate came back"
    assert sum(r.answered for r in rates) == 2


def test_weak_topics_are_a_rate_over_recent_answers(session, client):
    sign_up(client)
    user = _user(session)
    # A single-subtopic set, so every answer lands in the same bucket. One
    # response per item: `uq_practice_response_item` forbids a second, which
    # is what stops a score being padded by resubmitting.
    parent = practice.build_set(
        session, user=user, subject="Mathematics", topic="Polygons"
    )
    rows = session.execute(
        select(PracticeItem).where(PracticeItem.set_id == parent.id)
    ).scalars().all()
    assert len(rows) > practice.WEAK_MIN_ANSWERS

    # Enough answers in one subtopic, mostly wrong, to clear both thresholds.
    for index, item in enumerate(rows[: practice.WEAK_MIN_ANSWERS + 1]):
        session.add(
            PracticeResponse(
                item_id=item.id,
                set_id=parent.id,
                user_id=user.id,
                subject="Mathematics",
                subtopic="Polygons",
                given="0",
                correct=index == 0,
            )
        )
    session.flush()

    weak = practice.weak_subtopics(session, user=user, subject="Mathematics")
    assert [r.subtopic for r in weak] == ["Polygons"]
    assert weak[0].rate < practice.WEAK_AT


# ------------------------------------------------------------------ building


def test_a_set_is_eight_different_questions(client, session):
    """Eight variants of one shape is drill, not practice."""
    sign_up(client)
    url = start(client)
    set_id = int(url.rsplit("/", 1)[1])

    rows = session.execute(
        select(PracticeItem).where(PracticeItem.set_id == set_id)
    ).scalars().all()
    assert len(rows) == practice.SET_SIZE
    assert len({r.template_id for r in rows}) == practice.SET_SIZE


def test_a_topic_set_stays_in_its_topic(client, session):
    sign_up(client)
    url = start(client, topic="Circle theorems")
    set_id = int(url.rsplit("/", 1)[1])

    rows = session.execute(
        select(PracticeItem).where(PracticeItem.set_id == set_id)
    ).scalars().all()
    assert rows
    assert {r.subtopic for r in rows} == {"Circle theorems"}


def test_every_item_carries_a_citation_back_to_the_corpus(client, session):
    """A wrong answer has to end somewhere real, not at generated prose."""
    from sabi.models import Chunk

    sign_up(client)
    url = start(client)
    set_id = int(url.rsplit("/", 1)[1])

    rows = session.execute(
        select(PracticeItem).where(PracticeItem.set_id == set_id)
    ).scalars().all()
    for row in rows:
        assert row.source_locator and row.source_doc_id
        found = session.execute(
            select(Chunk.id).where(Chunk.locator == row.source_locator).limit(1)
        ).scalar_one_or_none()
        assert found is not None, (
            f"{row.template_id} cites {row.source_locator}, which is not in the corpus"
        )


def test_a_set_is_reproducible_from_its_stored_parameters(client, session):
    """The row is the question, so it cannot drift from what is marked."""
    sign_up(client)
    url = start(client)
    set_id = int(url.rsplit("/", 1)[1])

    for row in session.execute(
        select(PracticeItem).where(PracticeItem.set_id == set_id)
    ).scalars():
        template = templates_mod.get(row.template_id)
        assert template is not None
        rebuilt = template.rebuild(row.params)
        assert rebuilt.question == row.question
        assert rebuilt.answer == row.answer


def test_starting_a_set_does_not_cost_a_question(client, session):
    """Practice runs no model and must not eat the daily allowance."""
    sign_up(client)
    before = client.get("/app").text
    remaining_before = re.search(r"<strong>(\d+)</strong> left", before)

    start(client)

    after = client.get("/app").text
    remaining_after = re.search(r"<strong>(\d+)</strong> left", after)
    assert (remaining_before is None) == (remaining_after is None)
    if remaining_before:
        assert remaining_before.group(1) == remaining_after.group(1)


def test_the_daily_set_cap_is_enforced(client, session, monkeypatch):
    """Unmetered is not the same as unbounded."""
    sign_up(client)
    monkeypatch.setattr(practice, "DAILY_SET_CAP", 1)

    start(client)
    r = client.post(
        "/practice/start",
        data={"subject": "Mathematics", "topic": "", "csrf_token": csrf(client, "/practice")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "notice=cap" in r.headers["location"]

    session.expire_all()
    assert len(session.execute(select(PracticeSet)).scalars().all()) == 1


def test_an_unknown_subject_is_refused_rather_than_silently_swapped(client):
    sign_up(client)
    r = client.post(
        "/practice/start",
        data={"subject": "Yoruba", "topic": "", "csrf_token": csrf(client, "/practice")},
    )
    assert r.status_code == 400


def test_a_practice_page_stays_within_the_reload_budget(client, session):
    """Same budget as the answer page, for the same reason.

    A student sitting a set reloads it once per question on a metered
    connection. The marked page is the heavy one -- it carries eight sets of
    working -- so that is the one measured.
    """
    sign_up(client)
    url = start(client)
    assert len(client.get("/practice").content) < 20_000
    assert len(client.get(url).content) < 20_000

    client.post(f"{url}/finish", data={"csrf_token": csrf(client, url)})
    marked = client.get(url).content
    assert len(marked) < 20_000, (
        f"the marked set page is {len(marked):,} bytes, over the 20,000 a "
        "student on metered data should have to reload."
    )


def _user(session):
    from sabi.models import User

    return session.execute(
        select(User).where(User.email_normalised.is_not(None))
    ).scalars().first()
