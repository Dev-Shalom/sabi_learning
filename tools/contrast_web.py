#!/usr/bin/env python
"""Check the web app's palette, and check that the palette is the palette.

The same two jobs `tools/contrast_check.py` does for the Jinja stylesheet, done
for `web/styles/tokens.css`. Kept as a second tool rather than folded into the
first because the two stylesheets have different token names and different
requirement tables, and one script trying to serve both would end up with a
mode flag and a table nobody reads.

Held to **WCAG 2.2 AA**: 4.5:1 for text, 3:1 for large text and for the
non-text parts of a control (v2 §5.5). The 3:1 allowance for large text is
refused for body copy, as it was in v1 -- a student reading a question on a
bright bus is not reading large text.

The second job is the one that keeps a system a system: **no colour literal may
appear anywhere in `web/` outside the token file.** A ratio table can only
vouch for colours it knows the names of, so a stray `#12B886` in a component
is invisible to the table no matter how thorough it is.

Run in CI, alongside the Python one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "web" / "styles" / "tokens.css"
WEB = ROOT / "web"

# The one file outside the stylesheet that may name a colour, and the only
# reason it may: `<meta name="theme-color">` is read before the stylesheet
# exists, so it cannot be var(--paper). The exemption is paid for below --
# MIRRORED checks that what it says still matches the tokens, so the escape
# hatch cannot quietly become a second palette.
THEME_COLOURS = ROOT / "web" / "lib" / "theme-colors.ts"
ALLOWED_FILES = {TOKENS, THEME_COLOURS}

# (exported constant, token it must equal, theme)
MIRRORED = [
    ("PAPER_LIGHT", "paper", "light"),
    ("PAPER_DARK", "paper", "dark"),
]
EXPORTED = re.compile(r"export const ([A-Z_][A-Z0-9_]*)\s*=\s*\"(#[0-9A-Fa-f]{6})\"")

# Directories that are not ours to police.
SKIP_DIRS = {"node_modules", ".next", "out", "dist"}

TOKEN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;")
ANY_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")

LIGHT_BLOCK = re.compile(r":root\s*\{(.*?)\n\}", re.DOTALL)
DARK_MEDIA = re.compile(
    r"@media[^{]*prefers-color-scheme:\s*dark[^{]*\{(.*?)\n\}", re.DOTALL
)
DARK_ATTR = re.compile(r":root\[data-theme=[\"']dark[\"']\][^{]*\{(.*?)\n\}", re.DOTALL)

BOTH = ("light", "dark")

# (foreground, background, minimum, what it is for, themes)
#
# `themes` names where the pair actually occurs. Checking a pair in a theme it
# never appears in produces a failure nobody can act on.
REQUIREMENTS = [
    # Body copy and headings.
    ("ink", "paper", 4.5, "body text on the page", BOTH),
    ("ink", "surface", 4.5, "body text on a card", BOTH),
    ("muted", "paper", 4.5, "secondary text", BOTH),
    ("muted", "surface", 4.5, "secondary text on a card", BOTH),
    # Green. Two tokens, and the split is the whole point: `primary` is a fill
    # and fails badly as text, so only `primary-text` is checked against a
    # light ground.
    ("primary-text", "paper", 4.5, "a link or green text", BOTH),
    ("primary-text", "surface", 4.5, "green text on a card", BOTH),
    ("primary-text", "primary-tint", 4.5, "text on a selected row", BOTH),
    # A fill keeps its own foreground, in BOTH themes. --ink on --gold is
    # 1.52:1 in dark, so a label that followed the theme would be unreadable.
    ("on-primary", "primary", 4.5, "a label on the primary button", BOTH),
    # Achievement.
    ("gold-text", "paper", 4.5, "gold-meaning text", BOTH),
    ("on-gold", "gold", 4.5, "a label on a gold fill", BOTH),
    # Wrong, and errors.
    ("danger", "paper", 4.5, "an error message", BOTH),
    ("danger", "surface", 4.5, "an error on a card", BOTH),
    ("danger", "danger-tint", 4.5, "text on a wrong-answer row", BOTH),
    # The focus ring is a non-text control part: 3:1 under WCAG 2.2, and it
    # matters more here than almost anywhere, because the JAMB simulator is
    # driven entirely from the keyboard.
    ("focus", "paper", 3.0, "the focus ring", BOTH),
    ("focus", "surface", 3.0, "the focus ring on a card", BOTH),
]


def channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def themes(css: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Token tables for both themes, plus the text of every declaring block."""
    light_blocks = LIGHT_BLOCK.findall(css)
    if not light_blocks:
        raise SystemExit(f"no :root block found in {TOKENS.name}")

    light: dict[str, str] = {}
    for block in light_blocks:
        light.update(dict(TOKEN.findall(block)))

    # Dark starts as a copy of light: a token the dark theme leaves alone keeps
    # its light value, which is how the cascade actually behaves.
    dark = dict(light)
    dark_blocks = DARK_MEDIA.findall(css) + DARK_ATTR.findall(css)
    for block in dark_blocks:
        dark.update(dict(TOKEN.findall(block)))

    return light, dark, light_blocks + dark_blocks


def stray_literals() -> list[str]:
    """Any colour literal in `web/` outside the token file."""
    found: list[str] = []
    for path in sorted(WEB.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in {".css", ".ts", ".tsx", ".js", ".jsx"}:
            continue
        if path.resolve() in {p.resolve() for p in ALLOWED_FILES}:
            continue
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for match in ANY_HEX.finditer(line):
                found.append(
                    f"{path.relative_to(ROOT)}:{number}  {match.group(0)}  "
                    f"{line.strip()[:70]}"
                )
    return found


def mirrored_drift(tables: dict[str, dict[str, str]]) -> list[str]:
    """Colours duplicated into TypeScript that no longer match their token."""
    if not THEME_COLOURS.exists():
        return [f"{THEME_COLOURS.relative_to(ROOT)} is missing"]

    declared = dict(EXPORTED.findall(THEME_COLOURS.read_text(encoding="utf-8")))
    problems: list[str] = []

    for name, token, theme in MIRRORED:
        want = tables[theme][token].upper()
        got = declared.get(name)
        if got is None:
            problems.append(f"{name} is not exported from {THEME_COLOURS.name}")
        elif got.upper() != want:
            problems.append(
                f"{name} is {got}, but --{token} in the {theme} theme is {want}"
            )

    # The other direction: an exported colour nobody checks is exactly the
    # second palette this file exists to prevent.
    unchecked = sorted(set(declared) - {name for name, _, _ in MIRRORED})
    problems += [
        f"{name} is exported but nothing checks it against a token"
        for name in unchecked
    ]
    return problems


# A fill, and the token that is NOT allowed to sit on it. `text-ink` on
# `bg-gold` is the mistake this file was written to catch: it passes review by
# eye in light mode and measures 1.52:1 in dark.
FILL_MISUSE = [("bg-primary", "on-primary"), ("bg-gold", "on-gold")]
BANNED_ON_FILL = ("text-ink", "text-muted")


def fill_misuse() -> list[str]:
    """A theme-flipping text colour written onto a fixed fill.

    Line-scoped and deliberately simple: it reads class names in source, not a
    rendered DOM, so it cannot see a fill and a label split across elements.
    It catches the common case -- both classes in one `className` -- which is
    how these get written.
    """
    found: list[str] = []
    for path in sorted(WEB.rglob("*.tsx")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for fill, correct in FILL_MISUSE:
                if fill not in line:
                    continue
                for banned in BANNED_ON_FILL:
                    if banned in line:
                        found.append(
                            f"{path.relative_to(ROOT)}:{number}  {banned} on "
                            f"{fill} -- use text-{correct}"
                        )
    return found


def main() -> int:
    if not TOKENS.exists():
        print(f"no token file at {TOKENS.relative_to(ROOT)}")
        return 1

    css = TOKENS.read_text(encoding="utf-8")
    light, dark, _ = themes(css)
    tables = {"light": light, "dark": dark}

    missing = sorted(
        {
            f"{name} ({theme})"
            for fg, bg, _, _, applies in REQUIREMENTS
            for theme in applies
            for name in (fg, bg)
            if name not in tables[theme]
        }
    )
    if missing:
        print(f"tokens missing from {TOKENS.name}: {missing}")
        return 1

    failures = 0
    for theme in ("light", "dark"):
        rows = [r for r in REQUIREMENTS if theme in r[4]]
        print(f"\n{theme}")
        print(f"  {'foreground':<14} {'background':<14} {'ratio':>6} {'min':>5}  use")
        for fg, bg, minimum, use, _ in rows:
            value = ratio(tables[theme][fg], tables[theme][bg])
            ok = value >= minimum
            failures += 0 if ok else 1
            print(
                f"  {fg:<14} {bg:<14} {value:>6.2f} {minimum:>5.1f}  {use}"
                f"{'' if ok else '   FAIL'}"
            )

    drift = mirrored_drift(tables)
    if drift:
        print(f"\n{THEME_COLOURS.relative_to(ROOT)} has drifted from the tokens:")
        for d in drift:
            print(f"  {d}")
        failures += len(drift)

    misuse = fill_misuse()
    if misuse:
        print("\na theme-flipping text colour on a fixed fill:")
        for m in misuse:
            print(f"  {m}")
        failures += len(misuse)

    strays = stray_literals()
    if strays:
        print(f"\ncolour literals outside {TOKENS.relative_to(ROOT)}:")
        for s in strays:
            print(f"  {s}")
        print(
            "\nEvery colour belongs to a named token. A literal here is one the "
            "table above cannot vouch for."
        )
        failures += len(strays)

    if failures:
        print(f"\n{failures} requirement(s) not met")
        return 1

    print("\nAA met in both themes, and every colour is a named token")
    return 0


if __name__ == "__main__":
    sys.exit(main())
