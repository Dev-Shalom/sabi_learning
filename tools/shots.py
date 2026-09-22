#!/usr/bin/env python
"""Screenshot every surface at phone and desktop width, in both themes.

The stylesheet carries a comment about a gutter bug that was "only visible by
looking at a screenshot at 360px", which is the argument for this script
existing. 360 is the width of the handsets this is built for; 1440 is what a
reviewer will open it on.

    python tools/shots.py                   # needs `sabi serve` running
    python tools/shots.py --base http://127.0.0.1:8000 --out docs/screenshots

Not part of the test suite and not a CI dependency: it needs a browser, and the
suite deliberately runs without one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# (slug, path, method, form data)
SURFACES = [
    ("landing", "/", "get", None),
    ("study", "/app", "get", None),
    ("answer", "/ask", "post", {"question": "Find the sum of the interior "
                                            "angles of a polygon with 12 sides"}),
    ("refusal", "/ask", "post", {"question": "How do I find the argument of a "
                                             "complex number in polar form?"}),
    ("login", "/login", "get", None),
    ("privacy", "/privacy", "get", None),
    ("waitlist", "/waitlist", "get", None),
    # The photo page as it actually ships: no vision key, so it says so and
    # offers the composer. Shooting the honest state is the point -- a
    # screenshot of an upload box that cannot work would be a lie.
    ("photo", "/photo", "get", None),
]

# Reached only by signing up, so they are captured in a second pass that
# creates a throwaway account and asks a few questions first.
ACCOUNT_SURFACES = [("dashboard", "/dashboard"), ("practice", "/practice")]

WIDTHS = [("360", 360, 3200), ("1440", 1440, 2400)]


def shoot_account(browser, base, out, label, width, height, theme, scale=1) -> int:
    """Sign up a throwaway account, ask a few questions, shoot the dashboard."""
    import time

    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=scale,
        color_scheme=theme,
        reduced_motion="reduce",
    )
    page = context.new_page()
    try:
        page.goto(base + "/app", wait_until="load")
        for question in (
            "Find the sum of the interior angles of a polygon with 12 sides",
            "The 5th term of an AP is 11 and the 9th is 23. Find the common difference.",
            "How do I rationalise the denominator of 1/(3 - root 2)?",
        ):
            page.fill("#question", question)
            page.click(".composer button[type=submit]")
            page.wait_for_load_state("load")

        page.goto(base + "/signup", wait_until="load")
        page.fill("#signup-email", f"shots-{label}-{theme}-{int(time.time())}@example.test")
        page.fill("#signup-password", "completing-the-square-2026")
        page.click("#panel-signup button[type=submit]")
        page.wait_for_load_state("load")

        written = 0
        for slug, path in ACCOUNT_SURFACES:
            page.goto(base + path, wait_until="load")
            page.wait_for_timeout(200)
            name = f"{slug}-{label}-{theme}.png"
            page.screenshot(path=str(out / name), full_page=True)
            print(f"  {name}")
            written += 1

        # A practice set, reached by pressing the real button, then marked --
        # the marked page is the one worth looking at, because it is where
        # the verdict colours and the working sit. Both are shot: an empty
        # set and a marked one lay out differently at 360.
        page.goto(base + "/practice", wait_until="load")
        page.click(".practice-start button[type=submit]")
        page.wait_for_load_state("load")
        page.wait_for_timeout(200)
        name = f"practice-set-{label}-{theme}.png"
        page.screenshot(path=str(out / name), full_page=True)
        print(f"  {name}")
        written += 1

        # By name, not position: the CSRF field is the first input in every
        # form here, so `.practice-answer input` resolves to a hidden field.
        answers = page.locator('.practice-answer input[name="given"]')
        for index in range(min(3, answers.count())):
            answers.nth(index).fill("150")
            page.locator(".practice-answer button[type=submit]").nth(index).click()
            page.wait_for_load_state("load")
            answers = page.locator('.practice-answer input[name="given"]')

        page.click("form[action$='/finish'] button[type=submit]")
        page.wait_for_load_state("load")
        page.wait_for_timeout(200)
        name = f"practice-marked-{label}-{theme}.png"
        page.screenshot(path=str(out / name), full_page=True)
        print(f"  {name}")
        written += 1
        return written
    finally:
        context.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--theme", default="both", choices=["light", "dark", "both"])
    ap.add_argument("--only", default="", help="one surface slug")
    # 1 for anything that gets committed -- a full-page 2x shot of the
    # landing page is over a megabyte. 2 when looking closely at detail.
    ap.add_argument("--scale", type=int, default=1, choices=[1, 2])
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed:  pip install playwright")
        print("then:                          python -m playwright install chromium")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    themes = ["light", "dark"] if args.theme == "both" else [args.theme]
    surfaces = [s for s in SURFACES if not args.only or s[0] == args.only]

    written = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for theme in themes:
                for label, width, height in WIDTHS:
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        device_scale_factor=args.scale,
                        color_scheme=theme,
                        # Deterministic shots: the one page-load animation
                        # would otherwise be captured mid-flight.
                        reduced_motion="reduce",
                    )
                    page = context.new_page()
                    for slug, path, method, data in surfaces:
                        url = args.base + path
                        if method == "get":
                            page.goto(url, wait_until="load")
                        else:
                            # Type into the real composer and press the real
                            # button, so the page is reached exactly the way a
                            # student reaches it -- and so the CSRF field that
                            # is already on the form comes along. An injected
                            # form of our own would be rejected as stale, and
                            # would silently screenshot the error page.
                            page.goto(args.base + "/app", wait_until="load")
                            page.fill("#question", data["question"])
                            page.click(".composer button[type=submit]")
                            page.wait_for_load_state("load")

                        # Open the first source panel: a screenshot of the
                        # product's hero element closed shows nothing.
                        if slug == "answer":
                            panel = page.locator("details.source").first
                            if panel.count():
                                panel.locator("summary").click()
                                page.wait_for_timeout(120)

                        page.wait_for_timeout(180)  # webfont paint

                        # A screenshot of an error page is worse than none: it
                        # looks like a product shot until somebody reads it.
                        if "stale form" in page.content():
                            raise SystemExit(
                                f"{slug}: the POST was rejected as stale -- the "
                                "capture would have been an error page"
                            )

                        name = f"{slug}-{label}-{theme}.png"
                        page.screenshot(path=str(out / name), full_page=True)
                        print(f"  {name}")
                        written += 1
                    # A second pass for anything behind a login.
                    if not args.only or any(
                        slug == args.only for slug, _ in ACCOUNT_SURFACES
                    ):
                        written += shoot_account(
                            browser, args.base, out, label, width, height,
                            theme, args.scale,
                        )
                    context.close()
        finally:
            browser.close()

    print(f"\n{written} screenshot(s) in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
