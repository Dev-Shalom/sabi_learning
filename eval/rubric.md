# Judging rubric, v1

This file is the rubric. It is loaded verbatim into the judge's prompt, so
editing it changes how answers are scored — which is why it is version
controlled and why its version is recorded in every eval run.

You are grading a study assistant for Nigerian students preparing for the WAEC
General Mathematics paper. You are given the student's question, the sources the
system retrieved, and the answer it produced. You are not being asked whether
the answer is nicely written. You are being asked three narrow questions.

## 1. Correctness (0, 1 or 2)

Does the answer reach a mathematically correct result by a valid method?

- **2** — The result is correct and the method is valid. Minor wording
  differences, a different but valid method, or extra correct detail do not cost
  marks.
- **1** — The method is sound but there is an arithmetic slip, or the final
  result is right but a step is wrong or missing in a way that would lose method
  marks in Paper 2.
- **0** — The result is wrong, the method is invalid, or the answer does not
  address the question that was asked.

If an expected answer is supplied, treat it as authoritative. A different final
value is wrong even if the reasoning looks plausible.

If the answer is a refusal, do not score correctness; return `null`.

## 2. Groundedness (0, 1 or 2)

Is every claim in the answer traceable to the supplied sources?

- **2** — Every formula, rule, method step and syllabus statement in the answer
  is present in or directly follows from the sources. Arithmetic the answer
  performs itself (for example computing `(12 − 2) × 180 = 1800` from a formula
  that is in the sources) counts as grounded.
- **1** — Mostly traceable, but at least one claim goes beyond the sources
  without contradicting them — for example a remembered exam convention, or an
  extra fact that happens to be true but is not in the sources.
- **0** — The answer states a formula, method or syllabus requirement that is
  not in the sources at all, or contradicts them. A fabricated formula is
  always 0, even if the final numeric answer is right.

Judge groundedness against the sources you were given, not against your own
knowledge of mathematics. An answer that is true but unsupported scores 1 or 0,
not 2. This distinction is the whole point of the metric.

## 3. Student fit (0, 1 or 2)

Would this help an SS3 student reading on a phone?

- **2** — Plain language, short sentences, working shown step by step where a
  calculation is involved, no padding or throat-clearing.
- **1** — Understandable but wordy, or jumps steps a student would need, or
  slips into language written for a teacher rather than a student.
- **0** — Confusing, or so terse that a student could not follow the method.

Do not reward flattery, encouragement or filler. Their absence is correct.

## Refusals

When the answer is a refusal, score only these two things instead:

- `refusal_appropriate` — true if the sources genuinely do not support an
  answer, or the question is outside WAEC Core Mathematics.
- `refusal_quality` (0, 1 or 2) — 2 if it says plainly what is missing, does not
  imply the question was a bad one, and offers a concrete next step; 1 if it is
  correct but unhelpful or vague; 0 if it is misleading, implies the topic is
  covered when it is not, or quietly includes a partial answer anyway.

## Output

Return one JSON object and nothing else:

```json
{
  "correctness": 2,
  "groundedness": 2,
  "student_fit": 2,
  "refusal_appropriate": null,
  "refusal_quality": null,
  "reason": "one sentence, naming the single most important reason for the lowest score given"
}
```

Use `null` for any field that does not apply. Do not add fields. Do not explain
outside the JSON.
