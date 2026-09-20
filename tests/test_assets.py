"""Budgets and inventories for the things the page loads and posts.

Two jobs here, both of which exist because the audience is on a cheap Android
handset over metered data and because the app is about to grow a lot of surface:

  - what a first visit costs in bytes, counting the stylesheet, the script and
    the webfonts, none of which any test measured before;
  - which forms exist, so that a state-changing POST cannot be added without
    something noticing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "sabi" / "api" / "static"

# Budgets are per asset class rather than one total, so a regression names
# itself. Each number is the current size with room to grow, not a round guess;
# raising one should mean writing down what it bought.
BUDGETS = {
    # Raised from 34,000 when the landing page landed. What it bought: the
    # resist-dye band edges, the editorial two-column section layout, the
    # subject list, the auth and dashboard surfaces, and a dark theme -- one
    # stylesheet covering every surface in the product. Still one file, still
    # no framework, and it gzips to roughly a fifth of this.
    # Raised again for the motion layer: the opening cover, the scroll
    # reveals, the hero deck and cross-document view transitions. Every one
    # of them is behind `prefers-reduced-motion` and every one degrades to
    # nothing without JavaScript.
    # 56,000 -> 68,000 for the motion layer: one easing vocabulary applied
    # across every surface, animated <details> panels, and the staggered
    # arrivals on the study, dashboard and landing pages. It is one file for
    # eight page types with no framework, and it gzips to roughly a sixth of
    # this. Everything in it is behind `prefers-reduced-motion`.
    "sabi.css": 72_000,
    # Raised from 12,000 for the opening cover, the scroll reveals and the
    # hero deck. Still one file, still ES5, still no build step and no
    # dependency -- and all three degrade to nothing with JavaScript off.
    "sabi.js": 18_000,
}

# Webfonts are the one asset that can quietly cost more than everything else
# combined. Subset and self-hosted, a display and a UI family land well inside
# this; a full unsubsetted variable font would not.
FONT_BUDGET_TOTAL = 140_000


def test_stylesheet_and_script_stay_within_budget():
    for name, budget in BUDGETS.items():
        path = STATIC / name
        assert path.is_file(), f"{name} is missing from {STATIC}"
        size = path.stat().st_size
        assert size < budget, (
            f"{name} is {size:,} bytes, over its {budget:,} budget. "
            "Either cut it back or raise the budget and say what it bought."
        )


def test_webfonts_stay_within_budget():
    fonts = sorted(STATIC.glob("fonts/*.woff2"))
    if not fonts:
        pytest.skip("no self-hosted webfonts yet")
    total = sum(f.stat().st_size for f in fonts)
    listing = ", ".join(f"{f.name} {f.stat().st_size:,}" for f in fonts)
    assert total < FONT_BUDGET_TOTAL, (
        f"webfonts total {total:,} bytes, over the {FONT_BUDGET_TOTAL:,} "
        f"budget ({listing}). Subset harder, or drop a weight."
    )


def test_no_font_is_loaded_from_a_third_party():
    """Fonts are self-hosted: no extra DNS and TLS, and no third party.

    The audience is mostly under 18, so a font CDN would put a request to
    someone else's server on every page a student loads.
    """
    css = (STATIC / "sabi.css").read_text(encoding="utf-8")
    templates = Path(__file__).resolve().parent.parent / "sabi" / "api" / "templates"
    sources = [css] + [
        p.read_text(encoding="utf-8") for p in templates.rglob("*.html")
    ]
    for text in sources:
        for host in ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit"):
            assert host not in text, f"{host} referenced; fonts must be self-hosted"


# ------------------------------------------------------------------- forms

# Every GET route that renders HTML, with the token needed to reach it. The
# inventory is the point: a new page with a POST form has to be added here.
HTML_ROUTES = [
    ("/", None),
    ("/app", None),
    ("/privacy", None),
    ("/waitlist", None),
    ("/thanks", None),
    ("/admin/review", "test-admin-token"),
]

FORM_TAG = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
POST_FORM = re.compile(r'<form\b[^>]*method=["\']post["\'][^>]*>', re.IGNORECASE)
ACTION = re.compile(r'action=["\']([^"\']*)["\']', re.IGNORECASE)


def rendered_pages(client):
    """Every HTML page this app serves on GET, plus an answer page."""
    pages = {}
    for path, token in HTML_ROUTES:
        headers = {"X-Admin-Token": token} if token else {}
        r = client.get(path, headers=headers)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        pages[path] = r.text

    r = client.post("/ask", data={"question": "What is sin 30?"})
    assert r.status_code == 200
    pages["/ask (answer)"] = r.text
    return pages


def test_every_state_changing_form_is_a_real_post_to_a_known_route(client):
    """No form may post somewhere this test does not know about.

    This is the inventory that a CSRF token has to reach. When one is
    introduced, the same enumeration asserts every form carries it -- which is
    the only way to catch the single form somebody forgot.
    """
    known = {"/ask", "/feedback", "/waitlist"}
    found: set[str] = set()

    for where, html in rendered_pages(client).items():
        for tag in POST_FORM.findall(html):
            match = ACTION.search(tag)
            action = match.group(1) if match else ""
            # Admin promote routes carry an id, so compare on the prefix.
            if action.startswith("/admin/review/"):
                continue
            assert action in known, (
                f"{where} posts to an unknown route {action!r}. Add it to this "
                "test, and make sure it is CSRF-protected and metered."
            )
            found.add(action)

    assert found, "no POST forms found at all -- has the composer moved?"


def test_no_form_uses_get_to_change_state(client):
    """A state-changing form must be a POST, or a link will trigger it."""
    for where, html in rendered_pages(client).items():
        for tag in FORM_TAG.findall(html):
            if "method=" not in tag.lower():
                # Jinja may render a search form with no method; a GET form is
                # only acceptable when it does not change anything.
                assert "action=" not in tag.lower() or "/ask" not in tag, (
                    f"{where} has a form with no method posting to /ask"
                )


# ------------------------------------------------------------------- security


def test_every_state_changing_route_verifies_a_csrf_token():
    """The check that stops the hole coming back.

    Four routes shipped with `require_login` and no token check -- saving and
    removing notebook entries, setting an exam date, signing out everywhere.
    The forms rendered a hidden field, submitted it, and nothing read it, so
    a page on another site could have made a signed-in student delete their
    own revision notes.

    The form-enumeration test above did not catch it, because it checks where
    forms post rather than what the handler does with the token. This one
    reads the route signatures.
    """
    import re
    from pathlib import Path

    from sabi.api.deps import CSRF_GUARDS

    source = (
        Path(__file__).resolve().parent.parent / "sabi" / "api" / "app.py"
    ).read_text(encoding="utf-8")

    routes = re.findall(
        r'@app\.post\("([^"]+)"[^)]*\)\s*\ndef (\w+)\((.*?)\n\):', source, re.S
    )
    assert routes, "no POST routes found -- has the app moved?"

    unguarded = [
        f"{path} ({fn})"
        for path, fn, args in routes
        if not any(guard in args for guard in CSRF_GUARDS)
    ]
    assert not unguarded, (
        "POST routes with no CSRF verification: " + ", ".join(unguarded)
    )


def test_the_responses_carry_the_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200

    expected = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }
    for header, value in expected.items():
        assert r.headers.get(header) == value, f"{header} missing or wrong"

    csp = r.headers.get("Content-Security-Policy", "")
    for directive in (
        "default-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
        "form-action 'self'",
    ):
        assert directive in csp, f"CSP is missing {directive!r}"


def test_the_one_inline_script_matches_the_hash_the_policy_allows(client):
    """Two copies of one script would drift, and silently.

    The only symptom of a mismatch is a script the browser quietly refuses to
    run, so the script is defined once in Python and the hash is computed from
    those exact bytes.
    """
    import re

    from sabi.api.app import BOOT_SCRIPT, INLINE_BOOT_SCRIPT_HASH

    page = client.get("/").text
    served = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert len(served) == 1, f"expected one inline script, found {len(served)}"
    assert served[0] == BOOT_SCRIPT, "the served script is not the hashed one"
    assert INLINE_BOOT_SCRIPT_HASH in client.get("/").headers[
        "Content-Security-Policy"
    ]


def test_production_refuses_to_start_on_a_development_secret():
    """A dev default that works is exactly why this has to be enforced."""
    import secrets

    from sabi.config import Settings, check_production_secrets

    # Development is deliberately unbothered: a clone should just run.
    assert not check_production_secrets(Settings(environment="dev"))

    # Production is not.
    assert check_production_secrets(Settings(environment="production"))

    # Nor is a value somebody "changed" without making it a secret.
    weak = Settings(
        environment="production",
        secret_key=secrets.token_urlsafe(48),
        ip_hash_salt="dev-local-salt",
    )
    assert check_production_secrets(weak)

    # A short admin token is a brute-forceable door that looks closed. The
    # test environment happens to set a 16-character one, which is how this
    # case got written: the check caught it.
    short_admin = Settings(
        environment="production",
        secret_key=secrets.token_urlsafe(48),
        ip_hash_salt=secrets.token_urlsafe(32),
        admin_token="test-admin-token",
    )
    assert check_production_secrets(short_admin)

    # Real secrets pass.
    good = Settings(
        environment="production",
        secret_key=secrets.token_urlsafe(48),
        ip_hash_salt=secrets.token_urlsafe(32),
        admin_token=secrets.token_urlsafe(32),
    )
    assert not check_production_secrets(good), check_production_secrets(good)
