"""Accounts: credentials, sessions, the identity merge, and the dashboard.

The dashboard tests exist because the first version of its topic query shipped
with an ambiguous column reference that every unit test passed straight over --
nothing rendered the page. Anything that runs SQL needs a test that actually
runs it.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import func, select

from sabi.accounts import passwords, recovery, service, throttle
from sabi.models import AuthSession, Request as RequestRow, User

EMAIL = "ada@example.test"
PASSWORD = "completing-the-square-2026"


def csrf(client, path="/app"):
    page = client.get(path)
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def sign_up(client, email=EMAIL, password=PASSWORD, **extra):
    data = {"email": email, "password": password, "csrf_token": csrf(client, "/signup")}
    data.update(extra)
    return client.post("/signup", data=data)


def log_in(client, email=EMAIL, password=PASSWORD):
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf(client, "/login")},
        follow_redirects=False,
    )


# ------------------------------------------------------------------ hashing


def test_a_password_verifies_and_a_wrong_one_does_not():
    stored = passwords.hash_password(PASSWORD)
    assert stored.startswith("scrypt$")
    assert PASSWORD not in stored
    assert passwords.verify_password(PASSWORD, stored)
    assert not passwords.verify_password(PASSWORD + "x", stored)


def test_verification_never_raises_on_rubbish():
    for stored in (None, "", "not-a-hash", "scrypt$x$y$z$a$b"):
        assert passwords.verify_password("anything", stored) is False


def test_two_hashes_of_one_password_differ():
    """Salted, so a stolen table cannot be attacked once for everybody."""
    assert passwords.hash_password(PASSWORD) != passwords.hash_password(PASSWORD)


# ------------------------------------------------------------------- signup


def test_signing_up_claims_the_identity_that_was_already_asking(client, session):
    """The whole design in one test.

    Signing up must not create a second identity: the questions asked before
    it are already yours, and the daily count must not reset.
    """
    client.post("/ask", data={"question": "What is sin 30?"})
    client.post("/ask", data={"question": "Simplify 27^(2/3) x 16^(-1/2)"})

    before = re.search(r"(\d+) of (\d+) free", client.get("/app").text)
    used_before = int(before.group(2)) - int(before.group(1))
    assert used_before == 2

    r = sign_up(client)
    assert r.status_code == 200

    users = session.execute(
        select(User).where(User.email_normalised == EMAIL)
    ).scalars().all()
    assert len(users) == 1, "signing up must claim the row, not add one"
    user = users[0]

    # The questions came with them, because the id never changed.
    asked = session.execute(
        select(func.count()).select_from(RequestRow).where(RequestRow.user_id == user.id)
    ).scalar_one()
    assert asked == 2

    # The count did not reset -- the cap rose instead.
    after = re.search(r"(\d+) of (\d+) free", client.get("/dashboard").text)
    used_after = int(after.group(2)) - int(after.group(1))
    assert used_after == 2, "signing up must not hand out a fresh allowance"
    assert int(after.group(2)) > int(before.group(2)), "the cap should rise"
    assert user.plan == service.ACCOUNT_PLAN


def test_signup_shows_recovery_codes_once_and_stores_only_hashes(client, session):
    r = sign_up(client)
    shown = re.findall(r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", r.text)
    assert len(shown) == recovery.HOW_MANY

    user = session.execute(
        select(User).where(User.email_normalised == EMAIL)
    ).scalar_one()
    assert recovery.remaining(session, user.id) == recovery.HOW_MANY

    # A code works exactly once.
    assert recovery.redeem(session, user, shown[0]) is True
    assert recovery.redeem(session, user, shown[0]) is False
    assert recovery.remaining(session, user.id) == recovery.HOW_MANY - 1


def test_the_same_address_cannot_be_used_twice(client):
    assert sign_up(client).status_code == 200
    from conftest import FormClient

    from sabi.api.app import app

    other = FormClient(app)
    other.get("/app")
    r = sign_up(other)
    assert r.status_code == 400
    assert "already an account" in r.text


@pytest.mark.parametrize(
    "email,password,expect",
    [
        ("not-an-address", PASSWORD, "email address"),
        (EMAIL, "short", "characters"),
    ],
)
def test_signup_rejects_bad_input_and_says_why(client, email, password, expect):
    r = sign_up(client, email=email, password=password)
    assert r.status_code == 400
    assert expect in r.text


# -------------------------------------------------------------------- login


def test_login_logout_and_the_login_wall(client):
    sign_up(client)
    dash = client.get("/dashboard")
    assert dash.status_code == 200

    token = re.search(r'name="csrf_token" value="([^"]+)"', dash.text).group(1)
    assert client.post("/logout", data={"csrf_token": token}).status_code == 200

    locked = client.get("/dashboard", follow_redirects=False)
    assert locked.status_code == 303
    assert locked.headers["location"] == "/login?next=/dashboard"

    back = log_in(client)
    assert back.status_code == 303
    assert back.headers["location"] == "/dashboard"


def test_a_wrong_password_is_refused_in_words_a_student_can_act_on(client):
    sign_up(client)
    r = client.post(
        "/login",
        data={"email": EMAIL, "password": "not-it-at-all", "csrf_token": csrf(client, "/login")},
    )
    assert r.status_code == 400
    assert "Wrong email or password" in r.text


def test_an_unknown_address_looks_exactly_like_a_wrong_password(client):
    """Otherwise the login form tells you which addresses have accounts."""
    r = client.post(
        "/login",
        data={"email": "nobody@example.test", "password": PASSWORD,
              "csrf_token": csrf(client, "/login")},
    )
    assert r.status_code == 400
    assert "Wrong email or password" in r.text


def test_repeated_failures_are_throttled(client, session):
    sign_up(client)
    for _ in range(throttle.MAX_PER_EMAIL):
        client.post(
            "/login",
            data={"email": EMAIL, "password": "wrong-one-here",
                  "csrf_token": csrf(client, "/login")},
        )
    # Even the correct password is now refused, and says what to do.
    blocked = client.post(
        "/login",
        data={"email": EMAIL, "password": PASSWORD, "csrf_token": csrf(client, "/login")},
    )
    assert blocked.status_code == 400
    assert "Too many attempts" in blocked.text


def test_a_session_is_stored_only_as_a_hash(client, session):
    sign_up(client)
    token = client.cookies.get("sabi_session")
    assert token
    rows = session.execute(select(AuthSession)).scalars().all()
    assert rows
    for row in rows:
        assert row.token_hash != token
        assert token not in row.token_hash


# ------------------------------------------------------------- second device


def test_logging_in_elsewhere_does_not_absorb_that_device_s_history(client, session):
    """A shared phone must not import a stranger's questions into your account."""
    from conftest import FormClient

    from sabi.api.app import app

    sign_up(client)
    owner = session.execute(
        select(User).where(User.email_normalised == EMAIL)
    ).scalar_one()

    # A second device with its own anonymous identity and its own question.
    other = FormClient(app)
    other.post("/ask", data={"question": "What is sin 30?"})
    stranger_questions = session.execute(
        select(func.count()).select_from(RequestRow).where(RequestRow.user_id != owner.id)
    ).scalar_one()
    assert stranger_questions >= 1

    assert log_in(other).status_code == 303

    # The owner's history is unchanged: nothing was merged in.
    mine = session.execute(
        select(func.count()).select_from(RequestRow).where(RequestRow.user_id == owner.id)
    ).scalar_one()
    assert mine == 0


def test_merge_moves_traffic_and_releases_the_address(client, session):
    """The explicit merge, which is the only thing that may move rows."""
    from sabi.limits import limiter

    sign_up(client)
    target = session.execute(
        select(User).where(User.email_normalised == EMAIL)
    ).scalar_one()
    source = limiter.get_or_create_user(session, "merge-source-device")
    session.add(
        RequestRow(user_id=source.id, question="q", question_norm_hash="h", client="web")
    )
    session.flush()

    moved = service.merge_user(session, source=source, target=target)
    assert moved >= 1
    assert source.merged_into_user_id == target.id
    assert source.email_normalised is None
    assert session.execute(
        select(func.count()).select_from(RequestRow).where(RequestRow.user_id == target.id)
    ).scalar_one() == 1


# ---------------------------------------------------------------- dashboard


def test_the_dashboard_renders_with_real_traffic(client):
    """Runs the topic SQL. The first version of it was ambiguous and 500ed."""
    client.post("/ask", data={"question": "Find the sum of the interior angles "
                                          "of a polygon with 12 sides"})
    client.post("/ask", data={"question": "What is sin 30?"})
    sign_up(client)

    r = client.get("/dashboard")
    assert r.status_code == 200
    assert EMAIL in r.text
    assert 'class="stat-figure"' in r.text
    assert 'class="meter"' in r.text


def test_the_dashboard_renders_for_a_brand_new_account(client):
    """An empty account must get an invitation, not a crash or a blank page."""
    sign_up(client)
    r = client.get("/dashboard")
    assert r.status_code == 200
    # Matched on the start of the class attribute rather than the whole of
    # it: the element legitimately carries spacing utilities alongside it.
    assert 'class="empty' in r.text, "no empty state on a new account"
    assert "/app" in r.text, "an empty state should point at what to do next"


def test_the_exam_date_can_be_set_and_cleared(client, session):
    sign_up(client)
    token = csrf(client, "/dashboard")

    client.post("/dashboard/exam-date", data={"exam_date": "2027-05-04", "csrf_token": token})
    user = session.execute(select(User).where(User.email_normalised == EMAIL)).scalar_one()
    session.refresh(user)
    assert user.exam_date is not None and user.exam_date.isoformat() == "2027-05-04"

    client.post("/dashboard/exam-date", data={"exam_date": "", "csrf_token": token})
    session.refresh(user)
    assert user.exam_date is None


def test_a_dashboard_is_not_reachable_without_logging_in(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
