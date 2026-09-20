"""The web surface: rendering, safety, feedback, and the admin boundary."""

from __future__ import annotations

import re

from sabi.api.render import render_answer, render_source


def test_answer_html_is_escaped():
    html = render_answer("<script>alert(1)</script> and 5 < 6", set())
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_citation_markers_become_links_to_their_panel():
    html = render_answer("The rule is this [SYL D1].", {"SYL D1"})
    assert 'class="cite"' in html
    assert 'href="#src-syl-d1"' in html
    assert ">SYL D1<" in html


def test_a_citation_with_no_panel_is_not_rendered_as_a_link():
    """A link that opens nothing is worse than plain text in this product."""
    html = render_answer("Trust me [EX 99].", {"SYL D1"})
    assert "cite" not in html
    assert "[EX 99]" in html


def test_numbered_steps_become_a_list():
    html = render_answer("1. First step\n2. Second step\n3. Third step", set())
    assert html.count("<li>") == 3
    assert "<ol" in html


def test_source_highlight_is_marked_once():
    body = render_source("A rule sentence here. Another sentence.", "A rule sentence here.")
    assert body.count("<mark>") == 1


def test_source_highlight_absent_when_nothing_matched():
    body = render_source("A rule sentence here.", None)
    assert "<mark>" not in body


# ----------------------------------------------------------------- the app


# The audience is on metered mobile data, so these are budgets, not trivia.
# They are split by how often a student loads the page: the landing page is
# seen once and is allowed to be richer, while the study and answer pages are
# reloaded all day and keep the original ceiling.
def test_the_study_page_renders_and_is_small(client):
    r = client.get("/app")
    assert r.status_code == 200
    assert len(r.content) < 20_000
    assert "Sabi can be wrong" in r.text


def test_the_landing_page_renders_within_its_own_budget(client):
    r = client.get("/")
    assert r.status_code == 200
    # Richer than the study surface on purpose -- a hero, four sections and an
    # FAQ -- but still a page, not an application.
    assert len(r.content) < 60_000
    # It says what the product will not do, not only what it will.
    assert "What Sabi will not do" in r.text


def test_the_answer_page_stays_within_the_reload_budget(client):
    r = client.post("/ask", data={"question": "What is sin 30?"})
    assert r.status_code == 200
    assert len(r.content) < 20_000


def test_the_landing_page_touches_no_database_and_sets_no_cookie(client):
    """A public page must not mint an identity for every crawler."""
    from sabi.db import session_scope
    from sabi.models import User
    from sqlalchemy import func, select

    with session_scope() as s:
        before = s.execute(select(func.count()).select_from(User)).scalar_one()
    r = client.get("/")
    assert r.status_code == 200
    assert "sabi_id" not in r.cookies
    with session_scope() as s:
        after = s.execute(select(func.count()).select_from(User)).scalar_one()
    assert after == before


def test_asking_a_question_renders_citations_and_the_disclosure(client):
    r = client.post("/ask", data={"question": "Find the sum of the interior angles "
                                              "of a polygon with 12 sides"})
    assert r.status_code == 200
    assert 'class="cite"' in r.text
    assert '<details class="source"' in r.text
    assert "Sabi can be wrong" in r.text
    assert "Show the source" in r.text


def test_the_page_works_without_javascript(client):
    """The composer is a real form and the panels are <details>."""
    r = client.get("/app")
    assert '<form class="composer" method="post" action="/ask"' in r.text
    r2 = client.post("/ask", data={"question": "What is sin 30?"})
    assert "<details" in r2.text


def test_the_cap_is_shown_before_it_is_hit(client):
    r = client.get("/app")
    assert "left today" in r.text
    assert re.search(r"\d+ of \d+ free questions left today", r.text)


def test_feedback_is_rejected_from_another_device(client):
    """A vote is only accepted from whoever asked.

    The stranger is a fully legitimate visitor with their own valid CSRF
    token -- so this tests the ownership check specifically, and would still
    fail if CSRF were the only thing standing in the way.
    """
    from conftest import FormClient

    from sabi.api.app import app

    r = client.post("/ask", data={"question": "What is sin 30?"})
    request_id = re.search(r'name="request_id" value="([^"]+)"', r.text).group(1)

    stranger = FormClient(app)
    stranger.get("/app")  # picks up a different anonymous id
    denied = stranger.post(
        "/feedback", data={"request_id": request_id, "vote": -1},
        headers={"Accept": "application/json"},
    )
    assert denied.status_code == 403


def test_a_post_without_a_csrf_token_is_rejected(client):
    """The protection itself, checked directly.

    `samesite=lax` is not enough on its own once a POST spends an allowance
    and writes a row, because of Chrome's Lax+POST grace window.
    """
    client.get("/app")
    r = client.post("/ask", data={"question": "What is sin 30?", "csrf_token": ""})
    assert r.status_code == 400

    bad = client.post(
        "/ask", data={"question": "What is sin 30?", "csrf_token": "not-the-token"}
    )
    assert bad.status_code == 400


def test_feedback_is_stored_with_everything_needed_to_reconstruct(client, session):
    from sqlalchemy import select

    from sabi.models import Feedback

    r = client.post("/ask", data={"question": "What is sin 30?"})
    request_id = re.search(r'name="request_id" value="([^"]+)"', r.text).group(1)

    ok = client.post(
        "/feedback",
        data={"request_id": request_id, "vote": -1, "reason": "wrong_method"},
        headers={"Accept": "application/json"},
    )
    assert ok.status_code == 200

    row = session.execute(select(Feedback)).scalars().one()
    assert row.vote == -1
    assert row.reason == "wrong_method"
    for key in ("question", "answer", "retrieved_refs", "model", "prompt_version"):
        assert key in row.snapshot


def test_admin_is_invisible_without_the_token(client):
    assert client.get("/admin/review").status_code == 404
    assert client.get("/admin/review", headers={"X-Admin-Token": "wrong"}).status_code == 404


def test_admin_opens_with_the_token(client):
    r = client.get("/admin/review", headers={"X-Admin-Token": "test-admin-token"})
    assert r.status_code == 200
    assert "Review queue" in r.text


def test_promoting_feedback_creates_a_golden_item(client, session):
    from sqlalchemy import select

    from sabi.models import Feedback, GoldenItem

    r = client.post("/ask", data={"question": "What is sin 30?"})
    request_id = re.search(r'name="request_id" value="([^"]+)"', r.text).group(1)
    client.post(
        "/feedback",
        data={"request_id": request_id, "vote": -1, "reason": "wrong_method"},
        headers={"Accept": "application/json"},
    )
    fb = session.execute(select(Feedback)).scalars().one()

    promoted = client.post(
        f"/admin/review/{fb.id}/promote",
        data={"corrected_answer": "sin 30 = 1/2", "expected_value": "1/2",
              "answerable": "yes"},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert promoted.status_code == 200

    item = session.execute(select(GoldenItem)).scalars().one()
    assert item.origin == "feedback"
    assert item.expected_value == "1/2"
    assert item.question == "What is sin 30?"
    # Promotion is a data move: the retrieved documents came across with it.
    assert item.expected_docs


def test_privacy_page_states_what_is_stored(client):
    """The page must state what is true now, not what used to be.

    This assertion is the tripwire the original author left for exactly this
    change: it asserted "no sign-up" and "never required", and accounts made
    both false. Asserting the new truths keeps the tripwire working rather
    than deleting it.
    """
    r = client.get("/privacy")
    assert r.status_code == 200
    text = r.text.lower()
    # Accounts exist and are optional: anonymous asking is the product's
    # differentiator and it survived.
    assert "optional" in text
    # Passwords are stored hashed, and the page names how.
    assert "scrypt" in text
    # Addresses are still one-way hashed, said in words a 16-year-old reads.
    assert "scrambled" in text
    # And the claims that accounts falsified are gone.
    assert "no sign-up" not in text
    assert "never required" not in text
