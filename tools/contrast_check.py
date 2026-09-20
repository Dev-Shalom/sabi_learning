"""Check the palette against WCAG, and check that the palette is the palette.

Two jobs, both reading the real stylesheet so that no claim can drift away from
what ships:

  1. Every pair in REQUIREMENTS meets its minimum ratio, in *both* themes. The
     light theme is read from `:root`, the dark theme from the dark override
     block, and a token the dark theme does not redefine is inherited from
     light. A design with two themes and one checked theme is a design with an
     unchecked theme.

  2. No colour literal appears anywhere outside the token declarations. This is
     the check that actually keeps a system a system: a ratio table can only
     vouch for colours it knows the names of, so a stray `#8C2F2F` three hundred
     lines down is invisible to job 1 no matter how thorough the table is.

Held to AA for body text (4.5:1) throughout. The large-text 3:1 allowance is
refused deliberately: a student reading a worked solution on a bright bus is not
reading large text.

Run in CI, ahead of the tests.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "sabi" / "api" / "static" / "sabi.css"

# A token declaration: `--indigo-8: #101A3C;`. Hex only, and deliberately so --
# the ratio maths below is sRGB, and accepting `oklch()` here would mean either
# reimplementing the conversion (easy to get subtly wrong) or, worse, silently
# skipping tokens it could not parse and reporting success.
TOKEN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;")

# Any hex literal at all, for job 2.
ANY_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")

# The blocks that may declare tokens. Everything else in the file is rules.
LIGHT_BLOCK = re.compile(r":root\s*\{(.*?)\}", re.DOTALL)
DARK_BLOCK = re.compile(r"\[data-theme=[\"']dark[\"']\][^{]*\{(.*?)\}", re.DOTALL)
DARK_MEDIA = re.compile(
    r"@media[^{]*prefers-color-scheme:\s*dark[^{]*\{(.*?)\n\}", re.DOTALL
)

# (foreground, background, minimum, what it is used for, themes)
#
# `themes` names where the pair actually occurs. Checking a pair in a theme it
# never appears in produces a failure nobody can act on -- saffron is never text
# on cotton in either theme, which is exactly why `bronze` exists.
BOTH = ("light", "dark")
REQUIREMENTS = [
    # Text on the indigo ground. The hero, the nav, the dark bands.
    ("cotton", "indigo-9", 4.5, "body text on the deepest ground", BOTH),
    ("cotton", "indigo-8", 4.5, "body text on the hero ground", BOTH),
    ("cotton", "indigo-7", 4.5, "body text on a raised dark surface", BOTH),
    ("indigo-2", "indigo-8", 4.5, "muted text on the hero ground", BOTH),
    # Evidence on dark.
    ("saffron", "indigo-9", 4.5, "a citation on the deepest ground", BOTH),
    ("saffron", "indigo-8", 4.5, "a citation on the hero ground", BOTH),
    ("indigo-9", "saffron", 4.5, "a label on a saffron fill", BOTH),
    # Text on paper.
    ("ink", "surface", 4.5, "body text", BOTH),
    ("ink-soft", "surface", 4.5, "secondary text", BOTH),
    ("ink", "surface-2", 4.5, "source panel body", BOTH),
    # Evidence on paper. `evidence` is bronze in light and saffron in dark,
    # which is the whole reason this table is theme-aware.
    ("evidence", "surface", 4.5, "a citation", BOTH),
    ("evidence", "surface-2", 4.5, "a locator on an open panel", BOTH),
    # Filled controls.
    ("on-accent", "accent", 4.5, "a label on the primary button", BOTH),
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
    """Token tables for light and dark, plus the text of every declaring block."""
    light_blocks = LIGHT_BLOCK.findall(css)
    if not light_blocks:
        raise SystemExit(f"no :root block found in {CSS.name}")

    light: dict[str, str] = {}
    for block in light_blocks:
        light.update(dict(TOKEN.findall(block)))

    # Dark tokens start as a copy of light: a token the dark theme leaves alone
    # keeps its light value, which is how the cascade actually behaves.
    dark = dict(light)
    dark_blocks = DARK_BLOCK.findall(css) + DARK_MEDIA.findall(css)
    for block in dark_blocks:
        dark.update(dict(TOKEN.findall(block)))

    return light, dark, light_blocks + dark_blocks


def check_no_stray_literals(css: str, declaring: list[str]) -> int:
    """Colour literals may only appear where tokens are declared."""
    allowed_spans: list[tuple[int, int]] = []
    for block in declaring:
        start = css.find(block)
        if start != -1:
            allowed_spans.append((start, start + len(block)))

    strays: list[tuple[int, str, str]] = []
    for match in ANY_HEX.finditer(css):
        if any(lo <= match.start() < hi for lo, hi in allowed_spans):
            continue
        line_no = css.count("\n", 0, match.start()) + 1
        line = css.splitlines()[line_no - 1].strip()
        strays.append((line_no, match.group(0), line))

    if not strays:
        return 0

    print(f"\ncolour literals outside the token blocks in {CSS.name}:\n")
    for line_no, literal, line in strays:
        print(f"  {CSS.name}:{line_no}  {literal}")
        print(f"      {line[:96]}")
    print(
        f"\n{len(strays)} stray literal(s). Give the colour a token and use the\n"
        "token, or the contrast table above cannot vouch for it."
    )
    return len(strays)


def main() -> int:
    css = CSS.read_text(encoding="utf-8")
    light, dark, declaring = themes(css)
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
        print(f"tokens missing from {CSS.name}: {missing}")
        return 1

    failures = 0
    for theme in ("light", "dark"):
        rows = [r for r in REQUIREMENTS if theme in r[4]]
        if not rows:
            continue
        print(f"\n{theme}")
        print(f"  {'foreground':<12} {'background':<12} {'ratio':>6}  {'min':>5}  use")
        for fg, bg, minimum, use, _ in rows:
            value = ratio(tables[theme][fg], tables[theme][bg])
            ok = value >= minimum
            failures += 0 if ok else 1
            flag = "" if ok else "   FAIL"
            print(
                f"  {fg:<12} {bg:<12} {value:>6.2f}  {minimum:>5.1f}  {use}{flag}"
            )

    failures += check_no_stray_literals(css, declaring)

    if failures:
        print(f"\n{failures} design requirement(s) not met")
        return 1
    print("\nall contrast requirements met, in both themes, with no stray literals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
