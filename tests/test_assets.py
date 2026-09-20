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
