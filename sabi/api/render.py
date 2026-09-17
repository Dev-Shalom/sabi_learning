"""Turn an answer into HTML.

Deliberately tiny and deliberately not a markdown library. The answer text comes
from a language model, so everything is escaped first and only three things are
then re-introduced: paragraph breaks, bold, and citation markers. A markdown
renderer would accept far more than that from an untrusted string.

The citation marker is the product's hero element, so it is built here rather
than by a regex in a template: the inline marker and the panel it points at have
to carry byte-identical text and the same anchor id, or the link a student is
being asked to trust is a link that does not work.
"""

from __future__ import annotations

import html
import re

CITATION = re.compile(r"\[([A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?)\]")
BOLD = re.compile(r"\*\*(.+?)\*\*")
NUMBERED = re.compile(r"^(\d+)\.\s+")


def anchor_id(locator: str) -> str:
    return "src-" + re.sub(r"[^A-Za-z0-9]+", "-", locator).strip("-").lower()


def render_answer(text: str, known_locators: set[str]) -> str:
    """Escape, then re-introduce paragraphs, bold and citation markers."""
    if not text:
        return ""

    # Reflow first. The corpus is hard-wrapped at 80 columns because it is
    # written to be read as source files, and the extractive answerer quotes it
    # verbatim. Rendering those wrap points as line breaks put a break in the
    # middle of every second sentence on a 360px screen.
    from sabi.textutil import reflow

    blocks = re.split(r"\n\s*\n", reflow(text).strip())
    out: list[str] = []

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        numbered = [ln for ln in lines if NUMBERED.match(ln)]
        if len(numbered) >= 2 and len(numbered) == len(lines):
            items = "".join(
                f"<li>{_inline(NUMBERED.sub('', ln), known_locators)}</li>" for ln in lines
            )
            out.append(f'<ol class="steps">{items}</ol>')
        else:
            body = "<br>".join(_inline(ln, known_locators) for ln in lines)
            out.append(f"<p>{body}</p>")

    return "\n".join(out)


def _inline(line: str, known_locators: set[str]) -> str:
    safe = html.escape(line, quote=False)
    safe = BOLD.sub(r"<strong>\1</strong>", safe)

    def cite(m: re.Match[str]) -> str:
        locator = m.group(1)
        if locator not in known_locators:
            # Not a source we can show. Render it as plain text rather than as a
            # link that goes nowhere -- a citation a student cannot open is
            # exactly the thing this product exists to avoid.
            return html.escape(m.group(0), quote=False)
        return (
            f'<a class="cite" href="#{anchor_id(locator)}" '
            f'data-locator="{html.escape(locator, quote=True)}">{html.escape(locator)}</a>'
        )

    return CITATION.sub(cite, safe)


def render_source(text: str, highlight: str | None) -> str:
    """The source panel body, with the matched span pen-underlined."""
    escaped = html.escape(text, quote=False)

    if highlight:
        needle = html.escape(highlight.strip(), quote=False)
        if needle and needle in escaped:
            escaped = escaped.replace(needle, f"<mark>{needle}</mark>", 1)

    # The corpus is markdown, so "**Answer: 1800 degrees.**" is a bold run, not
    # four asterisks a student should have to read past.
    escaped = BOLD.sub(r"<strong>\1</strong>", escaped)

    blocks = re.split(r"\n\s*\n", escaped.strip())
    parts = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        parts.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(parts)


def attribution_label(attribution: str) -> str:
    return {
        "syllabus": "WAEC syllabus",
        "worked_example": "Worked example",
        "past_question": "Past question",
    }.get(attribution, "Source")
