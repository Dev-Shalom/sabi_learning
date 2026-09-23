# The redirection — what is kept, retired, reversed, and how we get there

Written in Phase 0, by the lead. Companion to `MASTER_PROMPT.md` (v2). The v1
brief is archived at `docs/archive/MASTER_PROMPT_v1.md` and is still the
authority on anything v2 does not mention.

---

## 1. The honest shape of this change

v2 calls it "adjustments, not a restart", and for the **backend** that is true.
For the product as a whole the ratio is worth stating plainly, because it
drives the schedule:

| | Lines | Fate |
|---|---|---|
| `sabi/retrieval/`, `sabi/answer/`, `sabi/llm/`, `evalharness/`, `sabi/limits/`, `sabi/accounts/`, `sabi/vision/`, `sabi/practice/` | ~13,000 | **Kept, largely as-is.** The hard-won part. |
| `sabi/api/app.py`, `deps.py`, `render.py` | ~1,400 | **Reworked** — HTML responses become JSON. Auth, CSRF and identity plumbing survive. |
| `sabi/api/templates/`, `sabi/api/static/` | ~4,500 (HTML + CSS + JS) | **Retired** with the Jinja UI. |
| `tests/test_web.py`, parts of `test_assets.py` | ~700 | **Retired**, replaced by Playwright. |
| The entire frontend | 0 today | **New.** |

So: the *system* is reused, the *product surface* is new. Nothing about the
grounded-answer machinery changes, which is the point — that machinery is the
reason to believe anything Sabi says.

### The three things that actually gate launch

Not the code. In order:

1. **Content.** §9 and §15 are clear: until the owner's legal consultation,
   only original Claude-drafted, teacher-reviewed questions may go live. A
   launch-wave of 13 subjects × several years × 2–3 papers is thousands of
   questions, each needing human review. **The Maths pilot (Phase 4 Step 1)
   measures the real cost per verified question, and that number sets the
   launch scope — not the other way round.**
2. **A real model call.** Never once done. Every groundedness and correctness
   number in this repo comes from the offline extractive provider and is a
   tautology under it. Phase 1 fixes this and the numbers may move.
3. **Legal.** See §4 below — there is a positioning tension the owner needs to
   resolve, not me.

---

## 2. Kept — binding, unchanged

Everything in v2 §5.1. The ones most likely to be quietly eroded under
schedule pressure, so they are repeated here:

- **Computed-never-typed answers**, verified by an independent test sharing no
  code with the generator. This survives into the content pipeline: §9.3 makes
  it the verification rule for every numeric question.
- **Citation validation** — invalid locators stripped; an answer with no valid
  citation is **discarded, not shown**.
- **Eval floors are never lowered to let code pass.** Selection rules are
  written before a sweep runs. Per-subject gates, not only global ones — with
  ~40 subjects this matters far more than it did with three (v2 trap 1).
- **No unmetered path**, including our own eval runs.
- **A new metered capability arrives switched off.**
- **The welfare guardrail runs before any model call and cannot be skipped.**
- **Anonymous-to-account claim keeps the same user id** and does not reset
  caps; **no automatic merge on a second device** (that device may be a
  sibling's or a cybercafé's).
- **Image bytes are never stored**; format from magic bytes.
- **Colour never carries meaning alone.**
- **When a test fails, establish which side is wrong before fixing either.**

The whole v1 trap list carries over as v2 §11.1 and is still live.

---

## 3. Retired — and how, so nothing is lost quietly

| What | When | Replaced by |
|---|---|---|
| `sabi/api/templates/**` (19 Jinja templates) | Phase 2, as each surface lands in `web/` | Next.js routes |
| `sabi/api/static/sabi.css` (~70 KB), `sabi.js` | Phase 2 | Tailwind v4 tokens + shadcn/ui |
| `tests/test_web.py` (21 tests), the byte-exact HTML string assertions | **One visible commit**, with the Playwright replacements in the same change (v2 trap 19) | Playwright, same behaviours |
| `tools/shots.py` Jinja surfaces | Phase 2 | Playwright screenshots at 360 px |

**The rule for retirement:** a Jinja surface is deleted only in the commit that
adds its Next.js replacement *and* the Playwright test asserting the same
behaviour. No orphan period, no quiet deletion. If a v1 test was asserting
something real — and most were — the new test asserts the same thing through
the new UI.

The three byte-exact strings v1 protected (`<form class="composer"…`,
`<details class="source"`, `name="request_id" value="`) die with the templates.
What they were protecting — that the composer is a real form, that sources are
disclosed, that an answer can be traced back to its request — becomes Playwright
assertions.

---

## 4. Reversed — each with its argument

These are v2 §5.2, logged in `DECISIONS.md` as required. Summarised here with
the caveats I am adding as lead.

| v1 | v2 | My note |
|---|---|---|
| No JS framework; works with JS off | Next.js + React | Accepted. Exam mode with keyboard control, autosave, offline and a server-authoritative timer is a real application, not a document. **Caveat kept in spirit:** landing, pricing and reading must render and be readable without JS — that is a test, not an intention. |
| Jinja is the UI | FastAPI becomes a JSON API | Accepted, no reservations. Two UIs would rot. |
| Byte-exact HTML assertions | Playwright | Accepted, with the one-commit rule above. |
| Adire indigo, Fraunces + Outfit | Verdant Ink, Sora + DM Sans | Owner's call. §7's contrast figures need re-measuring from the real token file by `tools/contrast_check.py` before Phase 2 ships — the brief's numbers are stated, not yet verified by our own tool. |
| No Alembic | Alembic in Phase 1 | Accepted and overdue. 19 tables becoming a full catalog. **Keep `tools/schema_drift.py` anyway** — it catches a different failure (ORM/DB divergence) than migrations do. |
| No password-reset email | Email + SMS arrive | Accepted; the original reason ("no transport exists") genuinely no longer holds. Ships switched off until tested end to end. Recovery codes stay as the offline path. |
| No client-side image downscaling | Downscale before upload | Accepted. Saves a student real money on metered data. |
| Three subjects, one board | All subjects, five bodies | Accepted — and this is the decision that drives §6. |

---

## 5. The retrieval-scoping decision — mine, and the one with real risk

**v2 flags this in Phase 0 and it deserves the space.**

### What v1 does

One partial HNSW index per `(exam_board, subject)` scope. Three scopes today.
The partial index exists because of v1 trap 1: a filter the ANN index does not
cover makes the walk exhaust `ef_search` and **silently return fewer rows than
`LIMIT` asked for**. Confining the walk to one scope makes `LIMIT 24` return 24.

### What that becomes at v2's scale

5 exam bodies × ~40 subjects = **up to 200 partial HNSW indexes on one table.**

I measured the cost rather than guessing:

| | Measured |
|---|---|
| Partial HNSW build | **1.67 ms/chunk** (201 chunks, 335 ms) |
| Partial index size | ~440–690 KB per scope at ~180 chunks |

Projected to 200,000 chunks, build time is ~5–6 minutes **and is driven by total
row count, not index count** — each row belongs to exactly one scope, so 200
indexes and 40 indexes cost about the same to build. Disk is ~100 MB, which is
nothing.

**So index count is not the real problem.** The real problem is content.

### The decision: scope by subject, tag by board

Per-`(board, subject)` scoping implies a **separate corpus per board per
subject**. WAEC Chemistry, NECO Chemistry, NABTEB Chemistry and JAMB Chemistry
examine substantially the same syllabus. Maintaining four corpora for one
subject means four times the authoring and review bill — and §15 makes clear
that human review cost is the binding constraint on this project.

So:

- **Retrieval scopes to `subject` only.** One partial HNSW index per subject
  (~40), predicate still a validated literal, trap 1 still respected.
- **Each document is tagged with the boards that examine it**
  (`exam_boards: [WAEC, NECO, JAMB]`), defaulting to all. Most content is
  board-agnostic.
- **Board is filtered in Python after retrieval**, exactly as exclusion chunks
  already are. This does *not* reintroduce trap 1, because the filter is
  applied to rows that have already been returned — the ANN walk is untouched.
  The cost is that a few of the 24 candidates may be discarded; because most
  content is shared, that is a small and measurable loss.
- **Exclusions stay board-specific.** "Not on this syllabus" genuinely differs
  between WAEC and JAMB, and those chunks are already on a separate query path
  (`exclusion_match`) with their own index, so they can carry a board predicate
  without touching the ANN path.
- **The answer cache key keeps the board.** v1 was right that a NECO Chemistry
  answer must never serve a WAEC Chemistry question — the *refusal boundary*
  differs even where the teaching does not.

**The measurement that must accompany this (Phase 7 acceptance):** the
proportion of retrieved candidates discarded by the board filter, per subject.
If it exceeds a threshold set before the measurement, the decision is wrong and
we go back to per-`(board, subject)` indexes and pay the content bill. Written
down now so it cannot be rationalised later.

---

## 6. The locator scheme

v1's citation regex is `\[([A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?)\]` and three
things depend on it agreeing exactly: the generator's validator, the UI
renderer, and `evalharness/scorers.py`. v1 deliberately avoided changing it.

It does not survive contact with ~40 subjects and past questions. `SYL A1`,
`PEX 1` and `CHM B1` work; `NECO 2019 P2 Q7` does not.

The scheme is specified in `docs/LOCATORS.md`. Changing the regex means
changing the validator, the renderer and the scorers **in one commit**, with
the eval re-run to prove citation validity is still 1.000 — that number is the
product's central claim and it is the one metric with zero tolerance.

---

## 7. The migration path, Jinja → API

Ordered so the system is never in a state where a student-facing surface has no
implementation.

1. **Phase 1.** FastAPI grows JSON endpoints *alongside* the Jinja routes.
   Nothing is deleted. The OpenAPI document is published and TypeScript types
   are generated from it. Both UIs work; only one is public.
2. **Phase 2.** `web/` gets the shell, the design system, auth. Still not
   public.
3. **Phases 3–8.** Each surface moves: its Next.js route lands, its Playwright
   test lands, and its Jinja template and `test_web.py` cases are deleted — in
   the same commit.
4. **Phase 9.** The Jinja router is removed entirely; `sabi/api/app.py` serves
   JSON only. Any template still present at this point is a surface someone
   forgot, and the commit says so.

**One origin throughout** (v2 §5.3, trap 14): Next.js and FastAPI behind one
domain with `/api` routed to FastAPI, so the session cookie stays first-party
and no CORS credential dance is ever needed.

---

## 8. What I am flagging to the owner

Recorded here because Phase 0 ends at a checkpoint and these are decisions I
should not make alone.

1. **A positioning tension.** §2.4 sets myschool.ng as the one to beat, and its
   pull is 60,000+ real past questions going back to 1978. §9.1 and §15 say
   only original, teacher-reviewed questions go live until the legal
   consultation. **Sabi cannot launch with a comparable past-question library
   under that constraint.** That is the right call on the law — but the
   marketing and the landing page must not imply a library we do not have.
   Either the positioning changes (better simulation, better tutor, honest
   explanations — not "more questions"), or the legal consultation moves
   earlier than Phase 9.
2. **The content bill is the schedule.** Everything else can be parallelised
   across agents; human review cannot. The Maths pilot should start as early as
   possible, in parallel with Phase 1, not after it.
3. **The eval numbers will move** the first time a real model is used, and they
   may move down. That is the measurement working, not a regression. Worth
   agreeing in advance so nobody treats an honest number as a failure.
