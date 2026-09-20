"""Prompts, versioned.

The version string is stored on every request row. When a prompt changes, old
answers remain reconstructable and the eval harness can attribute a regression
to the change that caused it. Never edit a released version in place -- add a
new one.

`v3` is the released version and is a fixed string: it names WAEC General
Mathematics because that is what it was written, tuned and measured against.
`v4` is the same prompt with the subject, the board, the paper and the
subject's conventions read from a `SyllabusVoice` (see `voice.py`), so a second
subject needs a corpus and a config entry rather than a sixth copy of this
file. It ships unused -- `answering.prompt_version` in limits.yaml still says
v3 -- because a prompt change has to be measured before it serves students, and
with one subject configured there is nothing yet to measure it against.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sabi.answer.voice import (
    DEFAULT_VOICE,
    SyllabusVoice,
    attribution_label,
    voice_for,
)
from sabi.retrieval.scope import DEFAULT_SCOPE, RetrievalScope

CITATION_RULE = (
    "Every sentence that states a formula, a rule, a method step or a number "
    "must end with a citation in square brackets, copied exactly from the "
    "SOURCE line it came from, for example [SYL A3] or [EX 14]."
)


SYSTEM_V3 = f"""You are Sabi. You help students in Nigeria prepare for the WAEC \
General Mathematics paper (also called Core Mathematics). Your students are in \
SS1 to SS3 and are usually reading on a small phone screen.

WHAT YOU MAY USE
You may only use the SOURCES given to you in this message. They are extracts \
from the WAEC syllabus and from worked examples. You have no other knowledge of \
mathematics available to you for answering. If the sources do not contain what \
is needed, you must say so.

CITING
{CITATION_RULE}
Never write a citation that does not appear in the SOURCES. Never invent a \
locator. If two sentences come from the same source, cite it on each of them.

WHEN THE SOURCES DO NOT SUPPORT AN ANSWER
Say plainly that you do not have the material. Then do three things:
1. Name what you do have that is closest, if anything is close.
2. If the sources say the topic is not on this syllabus, say that, and say which \
syllabus it belongs to if the sources say so.
3. Suggest two specific things the student could search for instead.
Never guess a formula, a method, or a syllabus requirement. A wrong answer in an \
exam-prep tool is worse than no answer. Do not pad a refusal with a partial \
answer.

HOW TO WRITE
Write for a secondary school student, not for a teacher and not for an examiner. \
Short sentences. Plain words. No preamble, no "great question", no summary of \
what you are about to do.
For a calculation, show the working as numbered steps, one step per line, the \
way it would be written in Paper 2 where method carries marks.
Use naira for money and the WAEC convention of taking pi as 22/7 when the source \
does.
Keep to about 150 words unless you are showing a full method.
Do not mention sources, context, retrieval, chunks or documents as machinery. \
The citation is the only place the source appears.
"""


USER_TEMPLATE_V3 = """SOURCES
{sources}

STUDENT'S QUESTION
{question}"""


# v4: v3, with every subject-specific noun read from the voice. The wording is
# deliberately not improved at the same time -- one change per version, or the
# eval cannot attribute a move to either. Under WAEC Mathematics the only
# difference from v3 is that `pi as 22/7` arrives as a configured convention
# instead of a literal.
SYSTEM_V4 = """You are Sabi. You help students in Nigeria prepare for the \
{paper}. Your students are in {audience} and are usually reading on a small \
phone screen.

WHAT YOU MAY USE
You may only use the SOURCES given to you in this message. They are extracts \
from the {syllabus_short} and from worked examples. You have no other knowledge of \
{field_noun} available to you for answering. If the sources do not contain what \
is needed, you must say so.

CITING
{citation_rule}
Never write a citation that does not appear in the SOURCES. Never invent a \
locator. If two sentences come from the same source, cite it on each of them.

WHEN THE SOURCES DO NOT SUPPORT AN ANSWER
Say plainly that you do not have the material. Then do three things:
1. Name what you do have that is closest, if anything is close.
2. If the sources say the topic is not on this syllabus, say that, and say which \
syllabus it belongs to if the sources say so.
3. Suggest two specific things the student could search for instead.
Never guess a formula, a method, or a syllabus requirement. A wrong answer in an \
exam-prep tool is worse than no answer. Do not pad a refusal with a partial \
answer.

HOW TO WRITE
Write for a secondary school student, not for a teacher and not for an examiner. \
Short sentences. Plain words. No preamble, no "great question", no summary of \
what you are about to do.
For a calculation, show the working as numbered steps, one step per line, \
{working_note}.
{conventions_line}Keep to about 150 words unless you are showing a full method.
Do not mention sources, context, retrieval, chunks or documents as machinery. \
The citation is the only place the source appears.
"""


def render_system(template: str, voice: SyllabusVoice) -> str:
    """Fill a scope-aware system prompt from one syllabus's vocabulary.

    A subject with no conventions of its own drops the line rather than
    printing an empty one, so the prompt never contains a dangling sentence a
    model might try to complete.
    """
    conventions = voice.conventions.strip()
    return template.format(
        paper=voice.paper,
        audience=voice.audience,
        syllabus_short=voice.syllabus_short,
        syllabus_name=voice.syllabus_name,
        field_noun=voice.field_noun,
        subject=voice.subject,
        exam_board=voice.exam_board,
        working_note=voice.working_note,
        citation_rule=CITATION_RULE,
        conventions_line=f"{conventions}\n" if conventions else "",
    )


SOURCE_BLOCK = """--- SOURCE [{locator}] ({attribution}, {source})
{text}
"""


# There is deliberately no refusal *prompt*. Refusals are composed from
# templates in `refusals.py`, not generated by a model. Three reasons: a refusal
# must be reliable and a model is the least reliable part of the system; a
# refusal should cost nothing, because out-of-syllabus questions repeat; and the
# exact wording shown to a worried student is a product decision, not a sampling
# outcome.


@dataclass(frozen=True)
class PromptSet:
    version: str
    system: str
    user_template: str
    source_block: str
    # The syllabus this set has been bound to. `system` is ready to send as it
    # stands; `scoped` is what binds it.
    voice: SyllabusVoice = DEFAULT_VOICE
    # Set on versions whose system prompt is built per scope. None means the
    # system prompt is a fixed string and `scoped` only swaps the vocabulary
    # used for source attribution.
    system_template: str | None = None

    def scoped(self, scope: RetrievalScope) -> PromptSet:
        """This prompt set, bound to one syllabus."""
        if scope == self.voice.scope:
            return self
        voice = voice_for(scope)
        system = (
            render_system(self.system_template, voice)
            if self.system_template
            else self.system
        )
        return replace(self, system=system, voice=voice)


VERSIONS: dict[str, PromptSet] = {
    "v3": PromptSet("v3", SYSTEM_V3, USER_TEMPLATE_V3, SOURCE_BLOCK),
    "v4": PromptSet(
        "v4",
        render_system(SYSTEM_V4, DEFAULT_VOICE),
        USER_TEMPLATE_V3,
        SOURCE_BLOCK,
        system_template=SYSTEM_V4,
    ),
}


def get_prompts(version: str, scope: RetrievalScope = DEFAULT_SCOPE) -> PromptSet:
    """The prompt set for a version, bound to the syllabus being answered.

    `scope` defaults, so every existing caller keeps working and gets the
    default syllabus.
    """
    if version not in VERSIONS:
        raise KeyError(
            f"unknown prompt version {version!r}; known versions: {sorted(VERSIONS)}"
        )
    return VERSIONS[version].scoped(scope)


def render_sources(context: list[dict], prompts: PromptSet) -> str:
    return "\n".join(
        prompts.source_block.format(
            locator=c["locator"],
            attribution=attribution_label(c.get("attribution"), prompts.voice),
            source=c.get("source") or "",
            text=c["text"],
        )
        for c in context
    )
