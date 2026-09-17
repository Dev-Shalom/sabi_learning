"""Check the palette's contrast ratios against WCAG, from the real CSS.

The design plan claims specific ratios. This reads the tokens out of
`sabi/api/static/sabi.css` and recomputes them, so the claim cannot drift away
from the stylesheet. Run in CI.

The brief is explicit that the milk background must not produce low-contrast
grey text, so the text tokens are held to AA for body text (4.5:1) rather than
to the large-text allowance.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "sabi" / "api" / "static" / "sabi.css"
TOKEN = re.compile(r"--([a-z-]+):\s*(#[0-9A-Fa-f]{6})\s*;")

# (foreground, background, minimum ratio, what it is used for)
REQUIREMENTS = [
    ("ink", "paper", 4.5, "body text"),
    ("ink-soft", "paper", 4.5, "secondary text"),
    ("mark", "paper", 4.5, "citations and refusals"),
    ("ink", "wash", 4.5, "source panel body"),
    ("mark", "wash", 4.5, "locator on an open panel"),
    ("paper", "ink", 4.5, "composer button label"),
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


def main() -> int:
    tokens = dict(TOKEN.findall(CSS.read_text(encoding="utf-8")))
    missing = [
        name
        for pair in REQUIREMENTS
        for name in pair[:2]
        if name not in tokens
    ]
    if missing:
        print(f"tokens missing from {CSS.name}: {sorted(set(missing))}")
        return 1

    failures = 0
    print(f"{'foreground':<10} {'background':<10} {'ratio':>6}  {'min':>5}  use")
    for fg, bg, minimum, use in REQUIREMENTS:
        value = ratio(tokens[fg], tokens[bg])
        ok = value >= minimum
        failures += 0 if ok else 1
        flag = "" if ok else "   FAIL"
        print(f"{fg:<10} {bg:<10} {value:>6.2f}  {minimum:>5.1f}  {use}{flag}")

    if failures:
        print(f"\n{failures} contrast requirement(s) not met")
        return 1
    print("\nall contrast requirements met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
