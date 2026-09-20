"""One guardrail rule, not a moderation system.

The users are minors. If a question is outside the subject and sounds like it
may involve something serious or personal, Sabi does not counsel, does not
assess risk, and does not try to be a helpline. It says what it is for and
points at a teacher or a trusted adult.

Deliberate design decisions:

* This runs **before** retrieval and before any model call. It must not depend
  on a model deciding to behave.
* The patterns are narrow and the response is written so that a false positive
  is harmless: told to a student who was only asking about maths, it reads as a
  slightly odd but kind non-answer, and it still tells them how to get a maths
  answer.
* There is no logging of the matched phrase and no separate storage. A student
  who types something painful does not get it filed somewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sabi.answer.voice import DEFAULT_VOICE, SyllabusVoice

# Narrow on purpose. Each pattern is a phrase a student would have to go out of
# their way to type; none of them appear in a maths question.
WELFARE_PATTERNS = [
    r"\bkill (myself|my self)\b",
    r"\bend (my life|it all)\b",
    r"\bno point (in )?living\b",
    r"\bwant to die\b",
    r"\bsuicid",
    r"\bhurt(ing)? myself\b",
    r"\bbeat(s|en|ing)? me\b",
    r"\bmy (father|mother|uncle|aunt|teacher|guardian|step ?father|step ?mother)\b.{0,40}"
    r"\b(beat|hit|touch|touches|touched|force|forced|threaten)",
    r"\btouch(es|ed)? me\b",
    r"\brape",
    r"\bafraid to go home\b|\bscared to go home\b",
    r"\brunning away from home\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in WELFARE_PATTERNS]

def welfare_response(voice: SyllabusVoice = DEFAULT_VOICE) -> str:
    """The one thing Sabi says here. Built per syllabus, worded identically.

    The subject is named twice, and both are the scope's own words: a student
    who asked a Physics question should not be told Sabi only does maths.
    """
    return (
        f"I can only help with {voice.label}, so I am not the right one to answer "
        "this, and I do not want to give you a poor answer on something that matters.\n\n"
        "Please talk to someone you trust about it today: a teacher you get on with, "
        "a school counsellor, a parent, or another adult in your family. If you are "
        "in danger right now, tell an adult near you straight away.\n\n"
        f"When you want to come back to {voice.casual_noun}, ask me anything on the "
        f"{voice.syllabus_short} and I will work through it with you."
    )


# The default syllabus's wording, for callers that only want to read the copy.
WELFARE_RESPONSE = welfare_response()


@dataclass(frozen=True)
class GuardrailVerdict:
    triggered: bool
    kind: str | None = None
    response: str | None = None


def check(
    question: str, voice: SyllabusVoice = DEFAULT_VOICE
) -> GuardrailVerdict:
    for pattern in _COMPILED:
        if pattern.search(question):
            return GuardrailVerdict(True, "welfare", welfare_response(voice))
    return GuardrailVerdict(False)
