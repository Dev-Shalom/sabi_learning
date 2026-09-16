"""Text shaping shared by the citation panel and the highlighter.

The corpus is hard-wrapped at about 80 characters because it is written to be
read and reviewed as source files. A phone at 360px must not inherit that: the
wrap points land in the middle of sentences, which makes a pen underline stop
halfway through a rule and makes the source panel look ragged.

`reflow` joins the wrap-lines back into logical lines while keeping the things
that are genuinely separate lines -- numbered solution steps, bullets, and the
bold Answer line -- on their own.
"""

from __future__ import annotations

import re

LIST_MARKER = re.compile(r"^\s*(?:\d+\.|[-*])\s+")
BOLD_LINE = re.compile(r"^\s*\*\*")


def reflow(text: str) -> str:
    out_blocks: list[str] = []

    for block in re.split(r"\n\s*\n", text):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        logical: list[str] = []
        for line in lines:
            starts_new = bool(LIST_MARKER.match(line)) or bool(BOLD_LINE.match(line))
            if not logical or starts_new:
                logical.append(line.strip())
            else:
                logical[-1] = f"{logical[-1]} {line.strip()}"
        out_blocks.append("\n".join(logical))

    return "\n\n".join(out_blocks)


def logical_lines(text: str) -> list[str]:
    """Reflowed lines, blank ones dropped. The units a highlight may cover."""
    return [ln.strip() for ln in reflow(text).splitlines() if ln.strip()]
