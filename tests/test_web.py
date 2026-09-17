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


def test_home_page_renders_and_is_small(client):
    r = client.get("/")
    assert r.status_code == 200
    # The audience is on metered mobile data. This is a budget, not a trivium.
    assert len(r.content) < 20_000
    assert "Sabi can be wrong" in r.text


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
    r = client.get("/")
    assert '<form class="composer" method="post" action="/ask"' in r.text
    r2 = client.post("/ask", data={"question": "What is sin 30?"})
    assert "<details" in r2.text


def test_the_cap_is_shown_before_it_is_hit(client):
    r = client.get("/")
    assert "left today" in r.text
    assert re.search(r"\d+ of \d+ free questions left today", r.text)


def test_feedback_is_rejected_from_another_device(client):
    from fastapi.testclient import TestClient

    from sabi.api.app import app

    r = client.post("/ask", data={"question": "What is sin 30?"})
    request_id = re.search(r'name="request_id" value="([^"]+)"', r.text).group(1)

    stranger = TestClient(app)
    stranger.get("/")  # picks up a different anonymous id
    denied = stranger.post(
        "/feedback", data={"request_id": request_id, "vote": -1},
        headers={"Accept": "application/json"},
    )
    assert denied.status_code == 403


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
    r = client.get("/privacy")
    assert r.status_code == 200
    for phrase in ["no sign-up", "scrambled", "never required"]:
        assert phrase.lower() in r.text.lower()
