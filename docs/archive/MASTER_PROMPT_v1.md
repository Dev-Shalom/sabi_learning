# Sabi — master prompt

> **What this file is.** Everything an agent needs to pick this project up cold:
> what it is, what has been built, every decision that must not be relitigated,
> every trap that has already been fallen into, and how the work is actually
> run. It is a working document — edit it, cut it, argue with it.
>
> **How to use it.** Paste it as the opening context for a new Claude session,
> or keep it in the repo and point at it. Section 12 is the part to hand a
> subagent; sections 5–9 are the part to keep for the lead.

---

## 1. What this is

**Sabi** is a study assistant for Nigerian SS3 students sitting the WAEC
examinations, covering Core Mathematics, Physics and Chemistry. It answers only
from retrieved syllabus text and worked examples, shows the source for every
claim, and refuses when retrieval does not support an answer.

**The audience is specific and it shapes everything.** Students in Nigeria, on
cheap Android handsets, over metered mobile data, often on shared school wifi
or behind carrier CGNAT, frequently studying weeks before the exam. Majority
under 18.

**The central claim, and the only one that matters:**

> Every claim traces to a retrieved chunk. The citation is the most carefully
> built thing on the page. The system says "I don't have that" instead of
> guessing.

A student two weeks from WAEC who gets a confident, plausible, wrong answer is
worse off than one who gets no answer. Every design decision in this repo
resolves toward that. When a trade-off is unclear, the tiebreaker is: *which
option makes it less likely that a student is told something false with
confidence?*

**Whether it actually does this is measured, not asserted.** That is what
`evalharness/` and `EVALUATION.md` are for, and it is the thing to protect
hardest.

---

## 2. Current state — verified, not remembered

| | |
|---|---|
| Branch | `redesign-accounts-and-subjects` |
| Commits | 29 |
| Python | ~24,500 lines across `sabi/`, `evalharness/`, `tools/`, `tests/` |
| Corpus | **170 documents, 538 chunks** |
| Subjects live | WAEC **Mathematics, Physics, Chemistry** |
| Tests | **571 passing, 1 skipped** |
| Database tables | 19 |
| pgvector | 0.8.6 |

### Corpus breakdown

| Subject | Syllabus docs | Worked examples | Locator prefix |
|---|---|---|---|
| Mathematics | 32 (`syl-*`) | 50 (`ex-01`…`ex-50`) | `SYL A1`, `EX 31` |
| Physics | 21 (`phy-syl-*`) | 21 (`phy-ex-*`) | `PHY A1`, `PEX 1` |
| Chemistry | 21 (`chm-syl-*`) | 25 (`chm-ex-*`) | `CHM B1`, `CEX 8` |

### Evaluation — the committed baseline

157 golden items in `eval/golden/seed.jsonl` (merged from `physics.jsonl` and
`chemistry.jsonl`).

| Slice | n |
|---|---|
| Answerable | 120 |
| Unanswerable — out of syllabus | 23 |
| Unanswerable — out of subject | 8 |
| Unanswerable — not in corpus | 4 |
| Unanswerable — welfare | 2 |
| …with a deterministic value check | 91 |

By subject: Mathematics 100, Physics 27, Chemistry 30.

| Metric | Value |
|---|---|
| Retrieval recall@k | **1.000** — and 1.000 in each subject separately |
| Retrieval precision@1 | 0.958 |
| Retrieval MRR | 0.976 |
| Citation validity | **1.000** (zero invalid locators in 157 answers) |
| Groundedness, fully grounded | 1.000 |
| Answer correctness (value check, n=91) | 0.989 |
| Unanswerable correctly refused | 0.892 |
| Over-refusal on answerable | 0.017 |
| Latency p50 / p95 | 41 ms / 74 ms |
| **Failures** | **7 of 157** |

**These come from the offline provider, not a language model.** Groundedness of
1.000 is a tautology — the offline answerer copies sentences out of the
retrieved context by construction. Correctness is measuring retrieval, not
reasoning. Never quote these numbers without that caveat; `EVALUATION.md` says
exactly which mean what.

### The 7 remaining failures, by name

| Item | Why |
|---|---|
| `g-009` | "What does a negative index mean?" — over-refused at 0.38. Four content words; little for hybrid retrieval to work with. |
| `g-037` | "What does the discriminant tell you?" — over-refused at 0.276. The term appears in one chunk and nowhere else, so there is no support mass. |
| `u-003` | Complex numbers — answered instead of refused. No Core topic excludes them, so nothing grounds a refusal. |
| `u-005` | Binomial theorem for negative index — same root cause. |
| `u-011` | Conic sections — same root cause. |
| `p-027` | "Question 4 on the 2019 WAEC physics paper 2" — `not_in_corpus`, the hardest kind: no syllabus section excludes a paper we simply do not have. |
| `c-002` | 5.6 dm³ of CO₂ — the syllabus doc contains the literal string "5.6 dm3" inside a *different* CaCO₃ calculation and ranks first; the extractive answerer quotes that. A generator failure, not a retrieval one. This single item is what the 0.98 value floor is pinned at. |

---

## 3. The stack, and why

FastAPI + Jinja2 + SQLAlchemy 2.0 + Postgres 16 with pgvector. Server-rendered
HTML. **No JS framework, no build step, no CDN, no third-party fonts, no
analytics.**

- **Works with JavaScript off.** The composer is a real form POST, source panels
  are `<details>`, auth is two real forms on one page. JS only upgrades:
  visible working state, in-place down-vote reason, an honest timeout message.
- **No API key required.** Offline deterministic providers run the whole system
  including the eval suite, which is what makes the numbers reproducible from a
  clean clone.
- Deployment target is Fly.io in **Johannesburg** — the closest region any usual
  host offers to Lagos. A round trip to eu-west costs 150–250 ms before the app
  does anything.

### Layout

```
corpus/          170 markdown documents with YAML provenance front matter
sabi/
  corpus/        loader, chunker, ingestion pipeline
  retrieval/     embeddings, pgvector + FTS store, RRF fusion, reranking, scope
  answer/        prompts, guardrail, refusals, cache, routing, the request path
  llm/           provider interface, Anthropic client, offline extractor, pricing
  accounts/      passwords, sessions, recovery codes, login throttle, identity
  practice/      question templates, set building, marking, weak topics
  vision/        photo validation, hashing, OCR cache, fixture client
  notebook/      saved answers with snapshotted citations
  limits/        metering, rate limiting, budget kill switch
  billing/       the payment seam. Unimplemented on purpose.
  obs/           structured logging, cost report, dashboard queries
  api/           FastAPI app, deps, templates, one stylesheet, two webfonts
evalharness/     the evaluation suite
eval/            golden dataset, rubric, committed baseline, threshold sweep
tools/           sweeps, contrast checker, schema drift, screenshots, generators
```

### Tables (19)

`documents`, `chunks`, `plans`, `users`, `requests`, `usage_events`, `feedback`,
`golden_items`, `answer_cache`, `system_state`, `waitlist`, `auth_sessions`,
`recovery_codes`, `login_attempts`, `notebook_entries`, `practice_sets`,
`practice_items`, `practice_responses`, `ocr_uploads`.

---

## 4. The answer path

```
question
   ├─ welfare guardrail ─────────── before any model call, cannot be skipped
   ├─ rate limiter ──────────────── daily cap, burst, IP backstop; no unmetered path
   ├─ budget kill switch ────────── cache-only past the monthly ceiling
   ├─ semantic cache ────────────── numeric guard: same shape, different numbers ≠ hit
   ├─ retrieval ─────────────────── Postgres FTS + pgvector, RRF fused, reranked,
   │                                sibling expansion; scoped to ONE syllabus
   ├─ refusal check ─────────────── grounded out-of-scope first, then confidence
   ├─ model routing ─────────────── Haiku default, Sonnet on low confidence
   ├─ generation ────────────────── answer from retrieved context only
   └─ citation validation ───────── invented locators stripped; no valid citation
                                    means the answer is DISCARDED, not shown
```

Every request writes a row with retrieved chunk ids, model, prompt version,
retrieval confidence, tokens, cost and latency — enough to reconstruct any
answer exactly when someone down-votes it three weeks later.

### Tuned thresholds — do not change without re-sweeping

| Setting | Value | How chosen |
|---|---|---|
| `refusal_threshold` | **0.40** | Midpoint of the 0.38–0.42 indifference band found by the sweep |
| `scope_exclusion_threshold` | **0.42** | Sweep |
| `cache.similarity_threshold` | 0.94 | — |
| `escalation_threshold` | 0.55 | — |
| `rrf_k` | 60 | (see trap 4 — this is load-bearing and subtly wrong) |
| `rerank_top_n` | 8 | |
| `final_context_chunks` | 4 | |

`tools/sweep_thresholds.py` runs a 5×5 grid, 25 full eval runs, under a
selection rule **fixed in the file before it runs**:

```
maximise   refusal.unanswerable_caught
subject to over_refusal_rate <= 0.03
       and value_pass_rate   >= 0.98
       and recall_at_k       >= 0.97
```

Ties break toward lower over-refusal: telling a student "I don't have this"
when the material exists is the failure they feel, and the one most likely to
make them stop using it.

---

## 5. Decisions taken — do not relitigate

These are settled. Each has reasoning in `DECISIONS.md`. Reopening one needs a
new argument, not a fresh opinion.

### Corpus and provenance
- Every document carries YAML front matter with `attribution` (`syllabus` /
  `worked_example` / `past_question`), `subject`, `exam_board`, `locator`.
- **Every syllabus document has a `## Not on this syllabus` section.** Without
  one, grounded refusal does not exist for that topic — it falls through to the
  weaker confidence threshold.
- Worked-example answers are **computed by a generator, never typed**, and a
  test recomputes them independently sharing no code.

### Retrieval
- Scoped to exactly **one (board, subject) pair per question**. A partial HNSW
  index exists per scope.
- **Explicit subject picker, no classifier.** A misclassified question retrieves
  the wrong corpus and then *correctly* refuses, and the student cannot tell
  why. The codebase already learned this: the exclusion index started as token
  overlap and caught 0 of 12.

### Identity and limits
- **Signing up claims the anonymous row; it never creates a new one.** Same
  `users.id`, so history follows with no backfill and the daily cap does not
  reset — which is also the correct anti-abuse answer.
- **Login on a second device does NOT merge.** That device may belong to a
  sibling, a shared phone, a cybercafé. Auto-merging imports a stranger's
  questions and poisons weak-topic detection. There is an explicit, confirmed,
  one-time offer, defaulting to no.
- Sessions are **rows, not signed cookies** — revocation, "log out everywhere",
  an active-devices list, and every route already holds a DB session.
- Passwords: `hashlib.scrypt`, no new dependency, params inside the stored
  value. **Login throttling is mandatory**, because scrypt at 16 MiB is itself
  a DoS lever.
- **No unmetered path.** Including our own: the eval harness runs as a real
  metered user on the `internal` plan.

### Interface
- Palette from **adire eleko**, Yoruba indigo resist-dyed cloth. The tonal
  indigo scale is a real material fact, each step a further dip.
  `--indigo-9 #0A1230` … `--cotton #F7F3EA`, saffron `#E5A72C` and bronze
  `#8A5A0B` for citations.
- Type: **Fraunces** (display) + **Outfit** (UI), self-hosted, 99.6 KB total.
  No Google Fonts CDN — extra DNS+TLS on a 3G audience, and a third party on a
  page aimed at minors.
- **One accent, one meaning.** Saffron on dark, bronze on paper: a citation, a
  refusal, or a correction. Never decoration. Two tokens because saffron on
  cotton is 1.9:1.
- Contrast is checked in CI from the real stylesheet, **in both themes**, and
  the checker **fails on any colour literal outside the token block**.
- Colour never carries meaning alone — right/wrong in practice always has a
  word beside it.

### Things deliberately not done
- **Alembic.** `create_all` plus a forward-only list of idempotent `ALTER`s in
  `sabi/schema.py:MIGRATIONS`. That list is a migration system in miniature and
  saying so is more honest than pretending `create_all` is enough. Becomes
  Alembic the day there is production data worth preserving.
- **Streaming answers.** Answers are short; streaming adds a failure mode (half
  an answer with half its citations) for little gain.
- **A moderation system.** One guardrail rule. A classifier for a 22-item risk
  surface is more code than judgement.
- **A password-reset email.** There is no email transport; a reset link that
  reports success and delivers nothing is the most damaging kind of
  working-looking feature. Five one-time recovery codes instead.
- **Client-side image downscaling.** Would be the first real JavaScript and
  would break "works with JS off" for one feature. A 5 MB limit instead.
  Revisit with a real user who hits it, not in advance.

---

## 6. Traps already fallen into — do not repeat

These cost real time. Each is a live hazard, not history.

**1. The HNSW post-filter problem.** `ORDER BY embedding <=> :vec LIMIT 24` with
a filter the index does not cover makes the ANN walk exhaust `ef_search` and
**silently return fewer rows than `LIMIT` asked for**. No error. Fixed with a
*partial* index per scope, which requires the predicate be a **literal, not a
bound parameter** — hence the character-whitelist-plus-allow-list double
validation in `sabi/retrieval/scope.py`. Any new filter on a vector query must
either be in the index predicate or be applied in Python after the rows return.

**2. `create_all` silently ignores columns added to an existing table.** A new
column with no `MIGRATIONS` entry passes on every fresh database and fails only
in production. `tools/schema_drift.py` exists because this happened twice.
**Run it after any model change.**

**3. Exclusion chunks are evidence for refusing, not material for answering.**
A "Not on this syllabus" chunk in answer context produced: *"what does a
negative index mean?"* answered with a list of Further Maths topics that are
not examined. Filtered in `pipeline._answerable`. Filtered **in Python, not
SQL** — see trap 1.

**4. RRF with `k=60` over 24-item lists flattens rank.** Every rank scores
between 1/61 and 1/84, so "present in both lists" outweighs "ranked first in
one". A question answered word-for-word by one worked example got a confident
explanation of average rate of reaction instead. Fixed by
`pipeline._shortlist`: each retriever's top 2 survive into the rerank shortlist
regardless of fused rank. **The underlying `rrf_k` is still arguably wrong and
is untouched because changing it moves every number.**

**5. A self-deadlock that looked environmental.** `viewer` wrote `last_seen_at`
holding a row lock while `answer_question` opened a second connection for the
same row. The suite went from 50s to 600s+. I initially called it
"environmental" — it was not. Fixed by committing the route session before
`answer_question` and only writing `last_seen_at` when stale. **Never dismiss a
slow test run as environmental without looking.**

**6. Never run two pytest sessions against the same test database.** They block
on `TRUNCATE ... CASCADE` and produce failures that look real. Seven "failures"
in one session were entirely this.

**7. Heredoc escaping mangles regexes and backslashes.** `\\n` and `\b` have
been silently corrupted more than once (`\b` became a literal `\x08`), and a
shell loop full of escaped regexes applied **zero** mutations while reporting
success. Use the `Edit`/`Write` tools for exact-string work, or write a Python
script to a file and run that.

**8. `str.replace` without a count** added a `scope` column to two models when
one was intended.

**9. `field: str` shadowed `dataclasses.field`.**

**10. Tests that were wrong, not the code.** Three separate times: a test
asserting `<mark>` is always present (`_highlight` correctly returns None when
nothing overlaps); `class="empty"` vs `class="empty mt-4"`; and
`d.meta.get("subject")` without a default marking all 82 Maths docs
unconfigured. **When a test fails, establish which side is wrong before fixing
either.**

### The AI-slop tell

The first design proposal was "deep ink + terracotta + warm paper". The
`frontend-design` skill names cream + serif display + terracotta as its **#1
generated-page tell**, and terracotta (`#D97757`) is Claude's own accent. This
was caught and replaced with adire indigo. **Watch for the house style of
generated design and refuse it deliberately.**

---

## 7. Evaluation discipline — the part to protect hardest

- **Selection rules are written before the measurement runs.** The sweep's rule
  is in the file above the grid so it cannot be rationalised afterwards.
- **A floor is never lowered because the code could not clear it.**
  `MIN_VALUE_PASS` went 0.98 → 0.97 once, pinned at **two named failures**, with
  the reasoning written in place. When both were later fixed by real changes, it
  went back **up** to 0.98. That round trip is the standard.
- **Per-subject recall is gated separately, and that is arithmetic.** Chemistry
  is 21 of 120 answerable items, so its recall could fall 1.00 → 0.90 and move
  the global figure by 0.0175 — inside the 0.02 global tolerance. A global
  scalar mathematically cannot see a single-subject regression. The gate
  discovers subjects from the run, so a new subject is covered from its first
  baseline.
- **Negative results are recorded with their numbers.** Filtering "What the
  syllabus requires" chunks out of answer context seemed obviously right and
  made everything worse (recall 1.000→0.983, over-refusal 0.017→0.042, failures
  7→12). It is in `EVALUATION.md` as a rejected remedy, not silently dropped.
- **Report what the numbers actually say.** A subagent once reported "all 9
  metrics identical to baseline" when the diff showed recall 0.9872→1.0000. The
  real numbers were reported instead.

---

## 8. The build sequence so far

| Phase | What |
|---|---|
| 0 | Corpus, retrieval, answer path, eval harness, web interface, CI — the measured prototype |
| — | **Product pivot.** The prototype was built to a brief that was the deliberate opposite of what the owner wanted: "paper, not chrome", zero webfonts, no navigation, no accounts, one subject. |
| 1 | Design system, landing page, adire palette, Fraunces + Outfit |
| 2 | Accounts, server-side sessions, CSRF, throttling, recovery codes, dashboard |
| 3 | Subject and exam-board scoping through retrieval; partial HNSW indexes |
| 4 | Physics: 21 syllabus docs, 21 worked examples, 27 golden items, thresholds re-swept |
| 5 | Notebook — saved answers with snapshotted citations |
| — | Production hardening: CSRF hole on 4 routes, security headers, refuse weak secrets |
| 6 | **Practice** — 64 parameterised templates across 3 subjects |
| — | **Chemistry switched on** — 3rd subject, 30 golden items, 2 retrieval faults fixed |
| — | Chemistry coverage gaps filled: organic, environment, qualitative analysis |
| 7 | **Photo input** — ships in its honest unavailable state |

### Practice (Phase 6) in detail

The 50 worked examples **are** the answer corpus — a student handed `ex-31` can
paste it into the composer and be handed the worked solution, and they overlap
the golden eval items. So practice uses **parameterised variants**: authored
template, sampled numbers, **answer computed in Python**, citation pointing at
the original locator.

- 64 templates: 37 Mathematics, 13 Physics, 14 Chemistry.
- Sets of 8, 15 minutes, marked by `sabi/valuematch.py`.
- **Nothing is marked until the set is closed** — otherwise a timed set becomes
  a guessing game against the marker. A closed set then refuses further answers.
- Weak topics are a **rolling correct-rate** over a subtopic's recent answers,
  floor of 4 answers. Explainable to a sixteen-year-old, which matters more
  here than a mastery model.
- Not metered against the question cap (no model call), but capped at 40
  sets/day: unmetered is not the same as unbounded.
- `practice_attempts` from the plan was **not built** — every set is sampled for
  one student, so a set and an attempt at it are the same row.

**Marking rule, stated explicitly:** a value is accepted if it equals the true
value **correctly rounded to the precision the student actually wrote**. So
`0.33` passes for one third and `1795` does not pass for 1800. A whole number
written without a decimal point is a claim of exactness, so `12` is not
accepted for 12.4 — without that rule the significant-figure test reads "12" as
two figures and lets it through, which is the one direction this must never be
wrong in.

### Photo input (Phase 7) in detail

- **A capability, not a provider.** `VisionClient` is its own ABC alongside
  `LLMClient`. `AnthropicLLM` implements both. `complete` untouched.
- **Nothing is asked automatically.** Transcribe → editable textarea → student
  presses Ask. A test asserts no `Request` row appears.
- **Image bytes are never stored.** `ocr_uploads` holds sha256, media type,
  size, transcription. The test checks the **column list**, so adding a `data`
  column fails the build.
- **Format from magic bytes**, never the declared content type.
- Metered on `plans.daily_ocr_cap` (5 free / 10 with account), not the question
  cap.
- Without a key, `NoVisionClient` raises and the page says so and offers the
  composer. **No heuristic OCR** — a hand-rolled reader's mistakes would be
  indistinguishable from a model's.

---

## 9. How the work is actually run — the agent workflow

Subagents were used heavily and productively. This is the pattern that worked.

### What to delegate

| Delegate | Keep |
|---|---|
| Corpus authoring (syllabus docs, worked examples) | Ingest and re-measurement |
| **Independent verification tests** | Threshold sweeps and their selection rules |
| Golden-set slices | Merging slices, regenerating the baseline |
| Bounded research | Every commit and commit message |
| | Any decision about what "good" means |

### The rules that made it work

1. **Name the exact files an agent may create or modify, and the ones it may
   not.** Every prompt listed both. Without this, agents edit config or eval
   files and the measurement becomes meaningless.
2. **Forbid `sabi ingest` and threshold edits in agent prompts.** Ingest changes
   every vector; it must happen once, with the eval run alongside it.
3. **Tell the agent to report doubt rather than ship it.** Every agent that was
   asked to flag uncertainty produced a genuinely useful list.
4. **Require a mutation test on any verification work.** "Break the thing you
   are checking and confirm your check fails." One agent ran 9 mutations; I ran
   7 on my own Chemistry checkers. A test that passes against a broken
   generator is worthless.
5. **Verify the agent's output yourself, on a sample.** I hand-checked seven of
   twenty-one Chemistry examples and every answer on two screenshots. Do not
   relay an agent's numbers as fact without this.

### What agents actually found

- **The practice-template verifier found 6 real defects** the arithmetic checks
  could not: a question naming the roots of a quadratic with a negative
  discriminant, "the 3th term", `4^(2/2)` as a fractional index, `1x + 1y`,
  `+ 0x`, a printed zero offset. **Its key insight, which should be standard:
  parse the *rendered question text*, not the stored parameters.** A checker fed
  params reproduces the generator's intended quantity perfectly while the
  sentence on screen asks for something else.
- **A corpus agent caught an error in my own brief** — I wrote "Zn3+", which
  does not exist. It used Zn2+ and said so.
- The Chemistry golden-slice agent reported honest first-run numbers including
  its own two failures, and flagged three corpus gaps that turned out to be
  real.

### Known friction

- Agents working concurrently report "unexplained changes in the tree" and
  "pre-existing failures" that are just the lead's in-flight work. Expected.
  Say so and move on.
- An agent's test file is not final until it reports. Running its tests
  mid-write produces confusing failures.
- Agents have been rate-limited mid-task. Retrying later worked.

---

## 10. House style

**Code.** Match the surrounding file's comment density, naming and idiom.
Comments explain *why*, especially why an obvious alternative was rejected —
this codebase is unusually heavily commented and that is deliberate.

**Commit messages.** Prose, not bullet lists. State what changed, what it fixes,
and the reasoning including rejected alternatives and measured numbers. Look at
`git log` before writing one. End with:
```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

**Product copy.** Plain, specific, never a dead end. No fake urgency. A refusal
says what it cannot do and what it can. Written for a sixteen-year-old under
pressure.

**Honesty in reporting.** If tests fail, say so with the output. If a step was
skipped, say that. State plainly when something is verified; do not hedge when
it is. Never claim a number that was not measured in this session.

### Byte-exact strings that tests parse — do not reformat

- `<form class="composer" method="post" action="/ask"` — `tests/test_web.py`
- `<details class="source"`
- `name="request_id" value="` with `name` before `value`
- The substring `"Sabi can be wrong"` in every subject's disclosure
- Citation regex: `\[([A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?)\]`

### Budgets enforced by tests

| | |
|---|---|
| Answer page, app home, practice pages | < 20,000 bytes |
| Landing page | < 60,000 bytes |
| `sabi.css` | < 72,000 |
| `sabi.js` | < 18,000 |
| Webfonts total | < 140,000 |

---

## 11. Verification — run all of these, in order

```bash
python tools/contrast_check.py      # both themes, no stray hex literals
python tools/schema_drift.py        # after ANY model change
python -m pytest -q                 # 571 passing, 1 skipped; real Postgres
python -m sabi.cli eval --baseline eval/baselines/current.json
python -m sabi.cli serve --port 8014   # then drive the real HTTP paths
python tools/shots.py --base http://127.0.0.1:8014 --theme both
```

**Then look at the screenshots at 360px.** Two real bugs were found only this
way: a locator wrapping mid-token (`EX` / `01`), and Practice being unreachable
on a phone because the masthead links hide below 1024px and the footer had no
link.

Setup: `docker compose up -d db` (Postgres 16 + pgvector on :5433), then
`python -m sabi.cli init && python -m sabi.cli ingest`.

---

## 12. Starting a task — the short brief

> Sabi is a WAEC study assistant (Mathematics, Physics, Chemistry) that answers
> only from retrieved syllabus text, cites every claim, and refuses rather than
> guesses. The audience is Nigerian SS3 students on cheap Android phones over
> metered data, majority under 18. The tiebreaker on any decision: *which
> option makes it less likely a student is told something false with
> confidence?*
>
> Read `DECISIONS.md` before proposing anything — it records what was decided
> and why, including what was deliberately not done. Read `EVALUATION.md`
> before touching retrieval, thresholds or the golden set.
>
> Rules:
> - Answers in generated content are **computed, never typed**, and verified by
>   a test that recomputes them independently.
> - Never change a tuned threshold without re-running `tools/sweep_thresholds.py`.
> - Never add a column without a `MIGRATIONS` entry; run `tools/schema_drift.py`.
> - Never add a state-changing POST without a CSRF guard.
> - A new metered capability must not arrive switched on.
> - If a test fails, establish which side is wrong before fixing either.
> - Report what you measured, including what got worse.

---

## 13. What is actually left

**Not more features.** Every phase in the plan has landed. What remains is the
honest gap:

1. **No API key has ever been used.** The Anthropic answering path, the Voyage
   embedder, the LLM-as-judge and the vision path are all written and tested
   against fakes. **No real inference call has ever been made.** Groundedness
   and correctness only become meaningful numbers when the suite runs against a
   real model.
2. **Not deployed.** `Dockerfile`, `docker-compose.yml` and `fly.toml` are here
   and the image builds clean. Deploying needs accounts and payment details.
3. **No real users.** This is a complete system that has not been put in front
   of anyone.
4. **Biology** — only a `tools/build_biology_examples.py` stub exists. It is
   also the least numeric subject, so the value-matching scorers transfer
   worst.
5. **Three known content weaknesses**, recorded in `EVALUATION.md`: short
   conceptual questions are the weak spot; you cannot refuse what nothing
   excludes (needs a corpus document listing what Core Maths excludes
   entirely); and conceptual answers can be quoted out of a document's
   objectives list.

**Ordered next steps if asked:**
1. Run the suite against Claude and the real judge.
2. Add the "what Core Mathematics excludes entirely" document — fixes 3 of 7
   remaining failures.
3. Deploy to Fly in Johannesburg and give the link to a handful of SS3 students.
4. Re-tune against real questions, because the golden set was written by
   someone who is not the user.
