"""The notebook, and the one property that makes it worth having.

A saved answer must still say the same thing in three weeks. The corpus will
have moved by then, so the test that matters here is the one that changes the
corpus underneath a saved entry and checks the entry did not move with it.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from sabi import notebook
from sabi.models import Chunk, NotebookEntry, Request as RequestRow, User

EMAIL = "keeper@example.test"
PASSWORD = "completing-the-square-2026"
QUESTION = "Find the sum of the interior angles of a polygon with 12 sides"


def csrf(client, path="/app"):
    return re.search(
        r'name="csrf_token" value="([^"]+)"', client.get(path).text
    ).group(1)


def sign_up(client, email=EMAIL):
    return client.post(
        "/signup",
        data={"email": email, "password": PASSWORD, "csrf_token": csrf(client, "/signup")},
    )


def ask(client, question=QUESTION):
    r = client.post("/ask", data={"question": question})
    found = re.search(r'name="request_id" value="([^"]+)"', r.text)
    assert found, "no request id on the answer page"
    return found.group(1), r


def keep(client, request_id, note=""):
    return client.post(
        "/notebook/save",
        data={"request_id": request_id, "note": note, "csrf_token": csrf(client)},
    )


# ------------------------------------------------------------------ the point


def test_a_saved_answer_does_not_change_when_the_corpus_does(client, session):
    """The whole reason the snapshot exists.

    A notebook that re-rendered live against today's corpus would quietly
    change what a student revised from -- which is the failure this product
    exists to prevent, arriving through a side door.
    """
    sign_up(client)
    request_id, page = ask(client)
    assert '<details class="source"' in page.text
    keep(client, request_id, note="for the mock")

    before = client.get("/notebook").text
    assert "interior angles" in before
    saved_source = re.search(
        r'<div class="source-body">(.*?)</div>', before, re.S
    )
    assert saved_source, "the saved entry has no source passage"
    saved_text = saved_source.group(1)

    # Now rewrite the chunks the answer cited, as a corpus edit would.
    row = session.execute(
        select(RequestRow).where(RequestRow.question == QUESTION)
    ).scalars().first()
    assert row is not None and row.cited_refs

    changed = 0
    for ref in row.cited_refs:
        chunk = session.execute(
            select(Chunk).where(Chunk.ref == ref)
        ).scalar_one_or_none()
        if chunk is not None:
            chunk.text = "This passage has been completely rewritten since."
            changed += 1
    session.flush()
    assert changed, "no chunks were changed, so the test proves nothing"

    after = client.get("/notebook").text
    assert "completely rewritten" not in after, (
        "the notebook re-read the corpus instead of its own snapshot"
    )
    assert saved_text[:80] in after


def test_the_saved_copy_reads_the_same_as_the_page_it_came_from(client):
    """Parity with the live answer, not the presence of any one element.

    The underline is only drawn when a sentence in the source genuinely
    overlaps the answer -- `_highlight` returns None otherwise, because a
    wrong underline is worse than none. So asserting a <mark> is always
    present would be asserting the wrong thing, and would fail on perfectly
    good answers. What must hold is that the saved copy matches what the
    student actually read.
    """
    sign_up(client)
    request_id, live = ask(client)
    keep(client, request_id)
    saved = client.get("/notebook").text

    assert '<details class="source"' in live.text
    assert '<details class="source"' in saved, "no source panel on a kept answer"
    assert "Sabi can be wrong" in saved, "the disclosure did not survive the save"

    # Every locator the live page showed is on the saved copy.
    live_locators = set(re.findall(r'class="locator">([^<]+)<', live.text))
    saved_locators = set(re.findall(r'class="locator">([^<]+)<', saved))
    assert live_locators, "the answer cited nothing, so there is nothing to check"
    assert live_locators <= saved_locators, (
        f"citations lost on save: {sorted(live_locators - saved_locators)}"
    )

    # And if the live page underlined a sentence, so does the saved copy.
    if "<mark>" in live.text:
        assert "<mark>" in saved, "the underline did not survive the save"


# ------------------------------------------------------------------ ownership


def test_keeping_needs_an_account(client):
    """An anonymous notebook would vanish when the browser is cleared."""
    request_id, page = ask(client)
    assert "Create a free account" in page.text
    assert 'action="/notebook/save"' not in page.text

    r = client.post(
        "/notebook/save",
        data={"request_id": request_id, "csrf_token": csrf(client)},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_you_cannot_keep_somebody_else_s_answer(client):
    from conftest import FormClient

    from sabi.api.app import app

    sign_up(client)
    mine, _ = ask(client)

    stranger = FormClient(app)
    stranger.get("/app")
    sign_up(stranger, email="stranger@example.test")
    r = stranger.post(
        "/notebook/save",
        data={"request_id": mine, "csrf_token": csrf(stranger)},
    )
    assert r.status_code == 403


def test_removing_is_scoped_to_the_owner(client, session):
    from conftest import FormClient

    from sabi.api.app import app

    sign_up(client)
    request_id, _ = ask(client)
    keep(client, request_id)
    entry = session.execute(select(NotebookEntry)).scalars().one()

    stranger = FormClient(app)
    stranger.get("/app")
    sign_up(stranger, email="stranger2@example.test")
    stranger.post(
        f"/notebook/{entry.id}/remove", data={"csrf_token": csrf(stranger)}
    )

    session.expire_all()
    assert session.get(NotebookEntry, entry.id) is not None, (
        "a stranger removed somebody else's entry"
    )


# -------------------------------------------------------------- the mechanics


def test_keeping_the_same_answer_twice_updates_rather_than_duplicates(client, session):
    sign_up(client)
    request_id, _ = ask(client)
    keep(client, request_id, note="first thought")
    keep(client, request_id, note="second thought")

    rows = session.execute(select(NotebookEntry)).scalars().all()
    assert len(rows) == 1
    assert rows[0].note == "second thought"


def test_a_long_note_is_trimmed_rather_than_rejected(client, session):
    sign_up(client)
    request_id, _ = ask(client)
    keep(client, request_id, note="x" * 5000)
    row = session.execute(select(NotebookEntry)).scalars().one()
    assert len(row.note) == notebook.MAX_NOTE


def test_an_empty_notebook_invites_rather_than_apologises(client):
    sign_up(client)
    page = client.get("/notebook").text
    assert "Nothing kept yet" in page
    assert "/app" in page


def test_the_entry_records_the_syllabus_it_came_from(client, session):
    sign_up(client)
    request_id, _ = ask(client)
    keep(client, request_id)
    row = session.execute(select(NotebookEntry)).scalars().one()
    assert row.subject == "Mathematics"
    assert row.exam_board == "WAEC"


def test_the_notebook_is_behind_a_login(client):
    r = client.get("/notebook", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
