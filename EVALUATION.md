# Evaluation

What is measured, how, the current numbers, and what it still gets wrong.

The failure list at the bottom is the part worth reading.

---

## The headline, with its caveat attached

| Metric | Value |
|---|---|
| Retrieval recall@k (answerable items) | **0.987** |
| Retrieval precision@1 | **0.936** |
| Retrieval MRR | **0.959** |
| Citation validity | **1.000** (0 invalid locators across 100 items) |
| Groundedness, mean ratio | **1.000** |
| Fully grounded answers | **1.000** |
| Answer correctness (deterministic value check, n=59) | **1.000** |
| Unanswerable questions correctly refused | **0.909** |
| Over-refusal rate on answerable questions | **0.026** |
| Latency p50 / p95 | **46 ms / 75 ms** |
| Cost per question | **$0.00143** (estimated — see below) |

**Read this before quoting any of it.** These numbers come from the *offline*
provider: a deterministic extractive answerer with no model behind it. It exists
so the whole system runs with no API key, which is also what makes these numbers
reproducible from a clean clone. It is not a language model, and three of the
figures above mean less than they look like:

- **Groundedness is 1.000, and that is a tautology, not an achievement.** The
  offline answerer copies sentences out of the retrieved context by
  construction, so of course every one of them traces back to it. A perfect
  score here should be read as "the measurement is wired up correctly and the
  context assembly is not dropping sources out from under the answer" — nothing
  more. The number only becomes informative the day it runs against Claude,
  which can paraphrase, infer and invent.
- **Correctness (1.000) is measuring retrieval, not reasoning.** The offline
  answerer quotes a worked solution verbatim; if the right solution was
  retrieved, the right number appears. A perfect score here means "retrieval
  found the right worked example 59 times out of 59", which is worth knowing and
  is not the same claim as "the maths was done correctly".
- **Cost is a price-list estimate, not billed spend.** No API call is made, so
  tokens are counted and priced at Haiku 4.5 rates to exercise the accounting.
  Every such row is flagged `cost_is_estimated` in the database and the report
  says so on its face.

The metrics that are fully real today: **retrieval**, **citation validity**,
**refusal behaviour**, **latency**, and the metering and cost machinery.

Running against Claude requires an API key and has not been done. That is a gap,
and it is the first thing to do next.

---

## How it is measured

`sabi eval` calls `answer_question` — the same entry point the web app uses,
through the same rate limiter, on the metered `internal` plan. It does not reach
inside retrieval or the generator. An eval that reaches in measures a system
that only exists inside the harness.

Caching is off for a run. A suite answering from cache measures the cache.

### The dataset

100 items in `eval/golden/seed.jsonl`:

| Slice | n |
|---|---|
| Answerable | 78 |
| Unanswerable — out of syllabus (Further Maths) | 12 |
| Unanswerable — out of subject (biology, history, physics…) | 5 |
| Unanswerable — not in corpus (specific past papers, grade boundaries) | 3 |
| Unanswerable — welfare | 2 |
| …of which have a deterministic value check | 59 |

Questions are written the way a student would type them, not lifted from the
corpus. Some reuse a worked example's numbers (testing retrieval); some ask for
the method in the abstract (testing whether the syllabus text is found instead).

The unanswerable slice is split four ways because these should fail *differently*
and a single "refusal rate" would hide which kind is broken. It did exactly that
early on: the first run scored 0.182 overall, and the split showed the whole
problem was out-of-syllabus at 0.000.

### The scorers

Deterministic first, in `evalharness/scorers.py`:

- **Retrieval** — scored at document level, not chunk level. Chunk indices move
  when a document is edited, and an eval set that breaks on a typo fix is an
  eval set nobody runs.
- **Citation validity** — every citation-shaped marker in the answer must have a
  panel behind it. This is the product's central claim, so it is zero-tolerance
  in CI rather than a score to improve.
- **Groundedness** — the fraction of substantive sentences whose content terms
  appear in the cited text. A traceability check, not a truth check.
- **Correctness** — a normalised substring check for a known value (`1800`,
  `2/9`, `(-5, 3)`), where one exists.
- **Refusal** — split by why the item is unanswerable, with a distinct failure
  mode for a welfare question that gets refused for the wrong reason.

Then the judge, in `evalharness/judge.py`. The rubric is `eval/rubric.md`, loaded
verbatim into the prompt and fingerprinted into every run, so a change to grading
is a reviewable diff. With no API key a **heuristic judge** stands in; every run
records which judge produced its numbers and the report prints it in the header.
The heuristic judge's "correctness" is really "did the expected value appear",
which is a weaker question than the rubric asks. The two are never averaged.

### Known weaknesses of the measurement itself

- **Unsourced numerals** are reported as a diagnostic, never a failure. A model
  that computes `(12 − 2) × 180 = 1800` produces a numeral that may appear
  nowhere in the sources even though the step is sound. 73 of 100 answers
  contain one. Flagging them as ungrounded would punish correct arithmetic.
- **The value check is a substring match.** An answer containing `1800` passes
  even if it says the answer is *not* 1800. The LLM judge exists to cover this;
  the heuristic judge does not.
- **59 of 78 answerable items have a deterministic check.** The other 19 are
  conceptual ("what does the discriminant tell you") and rest on the judge.

---

## Tuning

The two refusal thresholds were chosen by `tools/sweep_thresholds.py`, a 5×5 grid
over `refusal_threshold` × `scope_exclusion_threshold`, 25 full suite runs. The
selection rule was written into the script *before* it ran:

```
maximise   refusal.unanswerable_caught
subject to over_refusal_rate <= 0.03
       and value_pass_rate   >= 0.98
       and recall_at_k       >= 0.97
```

Chosen: `refusal_threshold = 0.46`, `scope_exclusion_threshold = 0.42`.

**The tradeoff that was rejected.** `refusal_threshold = 0.50` catches more
unanswerable questions (0.955 against 0.909) but pushes over-refusal to 0.038 —
three answerable questions refused instead of two. The rule was fixed in advance
and it says no, so the answer is no. Stated here because it is a real product
judgement, not an arithmetic one: telling a student "I don't have this" when the
material is right there is the failure they feel, and the one most likely to make
them stop using it.

The grid is in `eval/sweeps/thresholds.json`.

One thing the sweep taught: **a corpus edit moves every number.** Rewriting two
"Not on this syllabus" sections to name the functions students actually type
(`sin x` rather than "trigonometric functions") improved retrieval recall to
1.000 in that run but moved refusal catch around, because the offline embedder
is fitted on the corpus and refitting shifts every vector. A production
embedding model is stateless and would not do this. The thresholds were re-swept
after the change rather than left stale.

---

## What it gets wrong

Four failures out of 100. All four are listed, with the reason.

| Item | Question | What happened |
|---|---|---|
| `u-003` | "Simplify (3 + 4i)(2 − i) where i is the square root of −1" | **Answered instead of refused.** Complex numbers are Further Maths, but no syllabus document says so in a section the exclusion index can find — the corpus lists what each *topic* excludes, and complex numbers belong to no Core topic, so nothing excludes them. Retrieval finds surds and algebra, confidence reaches 0.54, and it answers. Fixing this properly means a corpus addition, not a threshold change. |
| `u-005` | "Expand (1 + x)^(−2) using the binomial theorem" | **Answered instead of refused.** Same root cause. "Binomial theorem" has no Core topic to be excluded from, and the question looks like an indices question (confidence 0.46). |
| `g-009` | "What does a negative index mean?" | **Retrieval miss, then over-refusal.** The right chunk (SYL A3) is not in the top results at all; the question is four content words long and "negative" and "index" are common across the corpus. Confidence 0.43 falls below the threshold and it refuses. Correct behaviour given bad retrieval, but the retrieval is the bug. This is the single item dragging recall@k to 0.987. |
| `g-037` | "What does the discriminant tell you?" | **Over-refused** at confidence 0.276. The syllabus text explains the discriminant under a heading about quadratic equations; the word "discriminant" appears three times in one chunk and nowhere else, so there is no support mass and the confidence formula punishes that. |

A fifth item, `g-077` ("What is the contrapositive of 'if p then q'?"), was on
this list until the last change and is not any more. It was never an answer
defect: the groundedness scorer was counting the citation marker itself as an
unsupported claim, because the tokens `ex` and `31` appear nowhere in the source
the citation points at. Moving the marker from its own line to the end of the
sentence it supports dropped the fully-grounded rate from 0.82 to 0.56 without
changing a single answer, which is how the bug was noticed. Citations are now
stripped before groundedness is scored. It is recorded here rather than quietly
deleted because a metric that moves when only formatting changed is worth
distrusting.

Two patterns worth naming:

1. **Short conceptual questions are the weak spot.** Both over-refusals are four
   or five words long. Hybrid retrieval has little to work with, the confidence
   formula reads thin support as uncertainty, and the system refuses. A student
   asking "what does the discriminant tell you" is asking a perfectly good
   question and getting nothing.
2. **You cannot refuse what nothing excludes.** Grounded refusal works by finding
   a syllabus section that says a topic is out of scope. Topics with no Core
   counterpart — complex numbers, the binomial theorem — have no such section, so
   they fall through to the confidence threshold, which is weaker. The fix is a
   corpus one: a document listing what the Core syllabus does not contain at all.

### Fixed along the way, by the harness

The first run scored 30 failures out of 100. All six failure modes it found were
real, and one of them was in the harness itself:

| Found | Was |
|---|---|
| Citation scorer | Read maths notation as citations. `S(n) = (n/2)[2a + (n−1)d]` counted as a fabricated source. Five false failures. |
| `_pick_primary` | Took the first Solution chunk in context regardless of document, so "volume of a cone" was answered with the **sphere's** worked solution. Correct, fully cited, and about a different solid. |
| `tokenize` | Dropped single characters, making `y = x` and `y = −x` identical to the retriever. |
| Chunker | Merged the short "Not on this syllabus" sections into their neighbours, leaving 1 of 13 with its heading. Grounded refusals caught **0 of 12**. |
| Confidence formula | Added agreement and support mass to the top score, handing out 0.30 before chunk quality was considered. "Explain photosynthesis" scored 0.37 on a best chunk of 0.12 and got answered. |
| Corpus text | Exclusion sections said "trigonometric functions" but never "sin x", which is what students type. |

Progress across the run:

| | First run | Now |
|---|---|---|
| Failures | 30 / 100 | 4 / 100 |
| Precision@1 | 0.859 | 0.936 |
| Citation validity | 0.950 | 1.000 |
| Value pass rate | 0.915 | 1.000 |
| Unanswerable caught | 0.182 | 0.909 |

---

## The remaining misses are kept as tests

`tests/test_behaviour.py` asserts that the two remaining out-of-syllabus misses
are *still* misses. Fixing one fails the build, which forces this file to be updated
instead of quietly going stale. That test has already caught itself once: after
the corpus edit, one of the three started refusing correctly and the build went
red until the list and the numbers here were corrected.

---

## CI

Every push runs the suite against a real Postgres with pgvector, gated two ways:

- `--baseline eval/baselines/current.json` catches a relative regression,
  including a small one a fixed floor would miss.
- `--fail-under` holds absolute floors, so a slow slide over several commits
  cannot walk the baseline downhill.

Citation validity has a tolerance of exactly zero.

---

## Reproducing this

No API key needed.

```bash
docker compose up -d db
pip install -e ".[dev]"
python -m sabi.cli init
python -m sabi.cli ingest
python -m sabi.cli eval
```

The run writes a full JSON record to `.eval-runs/`, including every item's
answer, retrieved refs, scores and judge verdict.
