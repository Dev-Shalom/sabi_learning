"""Signing up and logging in over JSON.

`tests/test_accounts.py` already proves the machinery: scrypt parameters,
session rotation, throttle windows, recovery codes. None of that is retested
here, because none of it is reimplemented -- the JSON endpoints call the same
`sabi/accounts/service.py` functions the Jinja forms do.

What is tested here is the part that is genuinely new, and it is all about
*failure*. A browser following a 303 can be handed back a form with a message
on it. A `fetch` cannot: it needs a status code it can branch on. Getting that
mapping wrong is how a client ends up retrying a rate limit immediately, or
showing "something went wrong" to somebody whose password was simply too
short.
"""

from __future__ import annotations

import re

import pytest

from sabi.api.v1.deps import CSRF_HEADER

PASSWORD = "a-long-enough-password-2026"


def csrf(client) -> str:
    page = client.get("/app").text
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def headers(client) -> dict:
    return {CSRF_HEADER: csrf(client)}


# ------------------------------------------------------------ the JSON-only path


def test_a_client_that_has_only_ever_spoken_json_can_write(client):
    """The path the Next app actually takes, with no Jinja page involved.

    Every other test here gets its CSRF token from `csrf()`, which reads a
    rendered Jinja page. That page sets the anonymous cookie on its way out, so
    those tests never exercised the case where `/api/auth/viewer` is the first
    thing a client ever calls -- which is exactly what a browser loading the
    Next app does.

    It was broken. The viewer endpoint minted an anonymous id to derive the
    token from and then did not set the cookie, so the next request minted a
    different one, the secrets did not match, and every write came back 403
    "This page has gone stale." Signing up from a clean browser was impossible,
    and no test could see it because they all went through Jinja first.
    """
    first = client.get("/api/auth/viewer")
    token = first.json()["csrf_token"]
    assert token, "the viewer endpoint must hand out a usable token"

    r = client.post(
        "/api/auth/signup",
        json={"email": "json-only@example.test", "password": PASSWORD},
        headers={CSRF_HEADER: token},
    )
    assert r.status_code == 201, (
        f"a JSON-only client was refused: {r.status_code} {r.text}"
    )


# ------------------------------------------------------------------ signing up


def test_signup_returns_the_recovery_codes_exactly_once(client):
    r = client.post(
        "/api/auth/signup",
        json={"email": "new@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    assert r.status_code == 201, r.text

    body = r.json()
    codes = body["recovery_codes"]
    # They are hashed before storage, so this response is the only occasion
    # they can ever be shown. A client that does not display them here has
    # lost them for the student.
    assert len(codes) == 5
    assert len(set(codes)) == 5

    # And the viewer in the body describes the person who now exists, not the
    # anonymous visitor who sent the request.
    assert body["viewer"]["authenticated"] is True
    assert body["viewer"]["display_name"] == "new@example.test"


def test_signup_keeps_the_identity_the_device_already_had(client):
    """No second user row: history follows the student in.

    This is also the anti-abuse answer. If signing up created a fresh row it
    would reset the daily allowance, and "clear the cookies and sign up again"
    would be free questions forever.
    """
    before = client.get("/api/auth/viewer").json()
    used = before["allowance"]["questions_cap"] - before["allowance"]["questions_remaining"]

    client.post(
        "/api/auth/signup",
        json={"email": "keeps@example.test", "password": PASSWORD},
        headers=headers(client),
    )

    after = client.get("/api/auth/viewer").json()["allowance"]
    assert after["questions_cap"] - after["questions_remaining"] == used


def test_a_second_account_on_the_same_address_is_a_conflict(client):
    client.post(
        "/api/auth/signup",
        json={"email": "taken@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    client.post("/api/auth/logout", headers=headers(client))

    r = client.post(
        "/api/auth/signup",
        json={"email": "taken@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    # 409, not 400: the request was well-formed, the address is simply in use.
    assert r.status_code == 409
    assert "log in" in r.json()["detail"]["message"].lower()


@pytest.mark.parametrize(
    "email,password",
    [
        ("not-an-email", PASSWORD),
        ("fine@example.test", "short"),
    ],
)
def test_a_rejected_signup_says_which_field_and_stays_a_400(client, email, password):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
        headers=headers(client),
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == "bad_request"
    # Plain, specific, never a dead end: the message is written to be shown to
    # a student as it is.
    assert detail["message"]
    assert not detail["message"].lower().startswith("error")


# --------------------------------------------------------------- logging in


def test_login_answers_with_the_person_who_just_logged_in(client):
    client.post(
        "/api/auth/signup",
        json={"email": "back@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    client.post("/api/auth/logout", headers=headers(client))

    r = client.post(
        "/api/auth/login",
        json={"email": "back@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    assert r.status_code == 200, r.text

    # The viewer is resolved before the request runs, so echoing it back would
    # answer `authenticated: false` to a successful login. It is recomputed.
    assert r.json()["authenticated"] is True
    assert r.json()["display_name"] == "back@example.test"


def test_a_wrong_password_is_401_and_says_nothing_about_the_address(client):
    client.post(
        "/api/auth/signup",
        json={"email": "real@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    client.post("/api/auth/logout", headers=headers(client))

    wrong = client.post(
        "/api/auth/login",
        json={"email": "real@example.test", "password": "not-the-password"},
        headers=headers(client),
    )
    absent = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.test", "password": "not-the-password"},
        headers=headers(client),
    )

    assert wrong.status_code == absent.status_code == 401
    # Identical wording, so the response does not reveal which addresses have
    # accounts. The timing is equalised in `service.log_in`.
    assert wrong.json()["detail"]["message"] == absent.json()["detail"]["message"]


def test_too_many_attempts_is_429_with_a_retry_after(client):
    client.post(
        "/api/auth/signup",
        json={"email": "throttled@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    client.post("/api/auth/logout", headers=headers(client))

    last = None
    for _ in range(8):
        last = client.post(
            "/api/auth/login",
            json={"email": "throttled@example.test", "password": "wrong-one"},
            headers=headers(client),
        )
        if last.status_code == 429:
            break

    assert last is not None and last.status_code == 429, "the throttle never fired"
    # Without this a client retries immediately, which is the behaviour the
    # throttle exists to stop.
    assert last.headers.get("Retry-After") == "900"
    assert last.json()["detail"]["code"] == "rate_limited"


# ------------------------------------------------------------------- logout


def test_logout_ends_the_session_and_is_safe_to_repeat(client):
    client.post(
        "/api/auth/signup",
        json={"email": "bye@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    assert client.get("/api/auth/viewer").json()["authenticated"] is True

    first = client.post("/api/auth/logout", headers=headers(client))
    assert first.status_code == 204
    assert client.get("/api/auth/viewer").json()["authenticated"] is False

    # Logging out twice is not an error. A client retrying on a dropped
    # connection must not be shown a failure for succeeding.
    again = client.post("/api/auth/logout", headers=headers(client))
    assert again.status_code == 204


def test_logging_out_hands_the_device_a_new_identity(client):
    """The shared-phone leak.

    Signing up claims the anonymous row rather than making a second one, so
    that questions asked before signing up follow the student in. The
    consequence, which was missed: after logging out the device's `sabi_id`
    still pointed at that row -- which now belonged to an account.

    The next person to pick up the phone -- a sibling, the next student in a
    cybercafe -- was anonymous, but *was the previous student's user row*. They
    were handed that account's daily allowance, their questions were written
    against that account's history, and the viewer endpoint told them the
    account's email address.
    """
    anonymous = client.get("/api/auth/viewer").json()
    assert anonymous["display_name"] is None
    anonymous_cap = anonymous["allowance"]["questions_cap"]

    client.post(
        "/api/auth/signup",
        json={"email": "shared@example.test", "password": PASSWORD},
        headers=headers(client),
    )
    account_cap = client.get("/api/auth/viewer").json()["allowance"]["questions_cap"]
    # Signing up is rewarded with a larger cap, which is what makes the leak
    # worth something to whoever inherits it.
    assert account_cap > anonymous_cap

    client.post("/api/auth/logout", headers=headers(client))

    after = client.get("/api/auth/viewer").json()
    assert after["authenticated"] is False
    assert after["display_name"] is None, "the next person is told whose phone this was"
    assert after["allowance"]["questions_cap"] == anonymous_cap, (
        "the next person inherited the account's allowance"
    )


# --------------------------------------------------------------------- CSRF


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/auth/signup", {"email": "csrf@example.test", "password": PASSWORD}),
        ("/api/auth/login", {"email": "csrf@example.test", "password": PASSWORD}),
        ("/api/auth/logout", None),
    ],
)
def test_no_csrf_token_no_write(client, path, body):
    """`SameSite=Lax` alone is not enough.

    Chrome's Lax+POST grace window will send a freshly minted cookie on a
    cross-site POST for about two minutes after it is set, which is exactly
    the window a signup lands in.
    """
    r = client.post(path, json=body) if body else client.post(path)
    assert r.status_code == 403
