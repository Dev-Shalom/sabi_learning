# Open items — to be settled before launch

Things noticed while building that were deliberately **not** fixed at the time,
because fixing them then would have been scope creep or premature. Each one is
recorded here with enough context to act on it later, and with the reason it
was left.

The owner asked for these to be held until the end of the project rather than
raised as they appeared. This file is that queue. Nothing here is a bug that
harms a student today; they are seams, promises and measurements that need
closing before real users arrive.

Reviewed at: **Phase 9, before the pilot.** Anything still open then is either
fixed or written into the launch notes as a known limitation.

---

## 1. Practice reuses `PracticeItem` for two different things

**Found:** Phase 1, building `/api/practice/sets`.

Generated-template practice (the 64 templates from v1) and bank-drawn practice
(past questions from the new catalog) both write to `practice_items`. The
bank-drawn path sets `template_id="bank"` as a sentinel and leaves `params`,
`hint` and `working` empty, because those fields exist for the template path.

**Why it was left:** it works, it is tested, and splitting the table mid-phase
would have meant a migration and a rewrite of both paths for no behavioural
gain.

**Why it matters eventually:** `sabi/practice/__init__.py` reads
`template_id` expecting a real template and `templates_mod.get()` returns
`None` for `"bank"`. Today nothing calls it with a bank-drawn set, so nothing
breaks — that is an accident of which code paths exist, not a property anyone
designed.

**What to do:** either a nullable `question_id` FK on `practice_items` with
`template_id` nullable, or two tables. Decide when the content pipeline
(Phase 4) shows which path students actually use.

---

## 2. `rrf_k = 60` is still arguably wrong

**Found:** v1, switching Chemistry on. Carried into v2 as trap 4.

Reciprocal rank fusion with `k = 60` over 24-item lists gives every rank a
score between 1/61 and 1/84, so appearing in *both* retriever lists outweighs
being ranked first in one. That is backwards for the case two retrievers exist
to cover.

**Why it was left:** `_shortlist` works around it by guaranteeing each
retriever's top two reach the reranker, which fixed the observed failures.
Changing `rrf_k` itself moves every retrieval number and would need a full
threshold re-sweep and a baseline regeneration.

**What to do:** sweep `rrf_k` alongside the refusal thresholds when the corpus
next changes materially — most likely Phase 7, when the tutor's corpus grows
across subjects and a re-sweep is happening anyway. Do not change it on its
own.

---

## 3. The eval numbers are a tautology until a real model runs

**Found:** v1. Still true.

Every groundedness and correctness figure in `EVALUATION.md` and every commit
message comes from the **offline extractive provider**, which copies sentences
out of the retrieved context by construction. Groundedness of 1.000 means the
measurement is wired up correctly, not that a model is behaving.

**Why it is not fixed:** there is no Anthropic key. Per master prompt v2 §15
item 4, that does not stall other work.

**What to do:** the moment a key exists, run the suite against Claude and the
real judge, record both sets of numbers side by side, and rewrite the headline
in `EVALUATION.md` so nobody quotes the offline figures as if a model produced
them. Expect them to move, possibly down. That is the measurement working.

---

## 4. Subject names and codes are unverified

**Found:** Phase 0, writing `contracts/subject_codes.yaml`.

All 46 subjects are marked `verified: false`. The list is drafted from general
knowledge of the Nigerian senior-secondary curriculum and has **not** been
checked against WAEC's, NECO's, NABTEB's or JAMB's published subject lists.

**Why it was left:** it does not block anything until content is authored, and
checking 46 subjects against four exam bodies is a research task in itself.

**What to do:** before Phase 4 authors content for a subject, confirm that
subject's row against the exam body's own syllabus and set `verified: true`
with the source. A wrong subject name is what a student picks in onboarding.

---

## 5. Four figures in the JAMB format are inferred, not read

**Found:** Phase 0, reading JAMB's Step-by-Step CBT Manual.

The manual confirms 2 hours, four subjects, 60 questions for Use of English
and 180 in total. The **40 questions per elective subject** follows from
180 − 60 over three subjects and matches every secondary source, but is not
shown directly in any screenshot.

Also: the shipped config is from the **2024** manual. `jamb.gov.ng` references
a "2027 JAMB Test Manual (Updated 18-09-2026)" whose path was not resolved.

**What to do:** before Phase 6 ships the JAMB simulator, find the current
manual and re-verify. `verified_on` and `source_url` exist on every format
config so this is possible; `stale_formats()` reports anything over a year old.

---

## 6. NECO's five options are probable, not confirmed

**Found:** Phase 0 research.

NECO objective papers appear to use **five** options (A–E) rather than four,
found consistently across independent past-paper transcriptions in several
subjects — but not confirmed at an official `neco.gov.ng` source.

**Why it matters:** a shared options component that hard-codes four would have
a student practising against three distractors when the real paper has four.
The schema and the loader already treat `option_labels` as configuration, so
the code is ready either way.

**What to do:** confirm at source before a NECO format config ships.

---

## 7. Paystack's webhook details are corroborated, not read at source

**Found:** Phase 0 research.

`paystack.com/docs/*` is behind Cloudflare and returns 403 to automated
fetchers. Every *technical* claim about webhook signing — HMAC-SHA512,
`x-paystack-signature`, the raw-body requirement — is corroborated across
independent secondary sources that agree with each other, but none was read at
origin. The *commercial* claim (₦8,000,000 Starter cap) **is** confirmed, from
`support.paystack.com`, which is not behind the same block.

**What to do:** open the docs in a real browser and confirm before the payment
handler is written in Phase 8. A webhook verified the wrong way is a payment
system that can be forged.

---

## 8. The Tailwind v4 browser floor needs a real measurement

**Found:** Phase 0 research; decided in `DECISIONS.md`.

Tailwind v4 requires Chrome 111+. The decision taken is that the app requires
a modern browser and says so, while the landing page, pricing and reading mode
stay legible without modern CSS or JavaScript.

**What to do:** measure it in Phase 2 on a real low-end Android handset,
including Opera Mini, rather than leaving the decision resting on reasoning.

---

## 9. The content bill is unmeasured, and it is the schedule

**Found:** Phase 0, writing `docs/REDIRECTION.md`.

Everything else can be parallelised across agents. Human review cannot. The
Mathematics pilot (Phase 4 Step 1) measures cost per verified question,
approval rate and edit rate, and **that number sets the launch scope** — not
the other way round.

**What to do:** start the pilot as early as possible, in parallel with other
phases rather than after them.

---

## 10. A positioning tension the owner has heard but not resolved

**Found:** Phase 0 checkpoint.

The brief sets myschool.ng as the one to beat, and its pull is 60,000+ real
past questions going back to 1978. §9.1 and §15 say only original,
teacher-reviewed questions go live until the legal consultation. Sabi cannot
launch with a comparable library under that constraint.

**Status:** acknowledged by the owner, not yet decided. Work proceeds on a
design that does not depend on the answer — the catalog holds a library of any
size and no copy claims a number.

**What to do:** settle before Phase 8 writes landing-page copy. Either the
positioning changes to simulation, tutor and honest explanations, or the legal
consultation moves earlier.

---

## 11. The exam route cannot meet the page-weight budget the brief sets

**Found:** Phase 2, measuring rather than estimating.

The brief sets 120 KB for the exam route (v2 §5.5). Measured on an exam page
that is still a placeholder, the route already costs **138.5 KB gzipped**, and
essentially none of it is ours:

| | gzip |
|---|---|
| react-dom | 70.1 KB |
| Next App Router client runtime | 44.0 KB |
| framework glue, CSS, route chunk | 24.4 KB |

127.3 KB of that is shared by every route and cannot be paid down by anything
written on the exam page. The 120 KB target and the decision to build the
frontend in Next.js are simply in conflict; no amount of care on the route
closes an 18 KB gap that exists before the first component.

**Status:** `tools/web_budget.py` enforces 155 KB total for the route, and
**18 KB for the route's own code** — the number the team can actually move,
and the tightest own-code budget in the table. So the route is genuinely
governed; it is the brief's specific figure that is not met.

**What to do:** an owner decision, not an optimisation.
- Accept ~138 KB as the floor and restate the brief's number, or
- alias `react`/`react-dom` to `preact/compat` (saves roughly 30–35 KB
  gzipped, and needs its own testing pass on hydration), or
- serve the exam route outside the App Router as a small hand-written client,
  which meets 120 KB comfortably but forks the frontend into two stacks.

Worth settling before the exam UI is built in Phase 5, because the third
option is much cheaper to choose before the code exists than after.

---

## 12. One endpoint is served but not in the frozen contract

**Found:** Phase 2, republishing the contract after the auth endpoints landed.

`tools/publish_openapi.py` reports:

    served but not in the contract (add them, or they are untyped):
      GET /catalog/topics/{subject_code}

The contract is frozen (v2 §10.2), so adding a path to it is a lead decision
rather than a tidy-up. Until it is in there, `openapi-typescript` generates no
type for it and any frontend call to it is unchecked — which is precisely the
thing the generated-types seam exists to prevent.

**Status:** the tool warns and does not fail, so this has been passing quietly.

**What to do:** either add the operation to `contracts/openapi.yaml`, or
decide it is internal and stop serving it under `/api`. Then make the warning
fail the build, because a warning nobody fails on is a warning nobody reads.

---

## 13. The bottom tab bar is a phone pattern, shown on desktop too

**Found:** Phase 2, looking at `docs/screenshots/home-1440-light.png`.

The brief asks for a bottom tab bar on phones (v2 §5.4), and that is what was
built — but there is no separate desktop navigation, so at 1440px the tab bar
sits pinned across the bottom of a wide screen where a top bar is conventional.

Nothing is broken: every section is reachable, the targets are large, keyboard
navigation works, and the e2e suite covers 1440px as well as 360px. It is a
question of whether it looks considered.

**Status:** deliberate for now. The audience is overwhelmingly on phones, and a
second navigation is a second thing to keep reachable and tested.

**What to do:** decide before the landing page in Phase 8, since that is the
surface most likely to be opened on a laptop — by a parent, or by a school.
