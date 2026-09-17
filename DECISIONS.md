# Decisions

Every choice here has a cost. This is what was traded away and why.

---

## Corpus and provenance

### No fabricated exam citations, anywhere

**Decision.** The corpus carries only provenance I can stand behind: sections of
the published WAEC syllabus (`SYL A3`) and worked examples authored in Paper 2
style (`EX 14`). No document claims a year or a question number.

**Why.** I do not have licensed access to WAEC past papers. Writing `2018 P2 Q7b`
on an item I had reconstructed would be inventing metadata — in a product whose
entire claim is that its citations can be trusted, printed in the hero element.
It is the exact failure the product exists to prevent.

**Cost.** The brief asked for past questions with worked solutions, and these are
authored items in that style instead. The corpus is therefore less
authoritative than the real thing.

**Mitigation.** Every numeric answer in all 50 worked examples is verified
against an independent computation in `tests/test_corpus.py`, and a test asserts
that no non-`past_question` document carries a year or question number, so the
rule cannot erode by copy-paste. Dropping in real licensed past papers later is
an ingestion job: write the markdown, run `sabi ingest`. No code changes.

### One subject, one board, 82 documents

SS3 WAEC Core Mathematics only. 32 syllabus documents, 50 worked examples, 188
chunks. A narrow corpus that can be evaluated proves more than a broad one that
cannot, and 100 golden items over 82 documents is dense enough for a retrieval
miss to be visible rather than lost in an average.

### Every syllabus document says what it does *not* cover

Each topic document ends with "Not on this syllabus". This is the single highest-
leverage piece of corpus design in the project: it makes refusals **grounded**.
The system can cite the line saying differentiating `sin x` is Further Maths,
rather than refusing because a number fell below a threshold.

The limit of it is in EVALUATION.md: a topic with no Core counterpart (complex
numbers) has no section to be excluded from, so nothing excludes it.

---

## Retrieval

### pgvector on Postgres, not a hosted vector database

**Decision.** pgvector, and no plan to move.

**Why.** 188 chunks. A hosted vector DB solves problems this project does not
have — sharding, billions of vectors, multi-tenant isolation — and creates ones
it does: a second datastore to keep consistent with the primary, a second
failure mode, a second bill, and network latency on the hot path for a corpus
that fits in a few megabytes of RAM.

Keeping vectors in Postgres also buys things that turned out to matter more than
ANN performance:

- The **hybrid query** is one database. Full-text ranking and cosine distance
  are computed side by side, and the exclusion query blends `ts_rank_cd` with
  vector similarity in a single SQL statement. Across two systems that is an
  application-level join over two network calls.
- **Transactional re-ingest.** Replacing a document's chunks and vectors is one
  transaction. With a separate vector store, a failure between the two leaves
  citations pointing at text that no longer exists.
- Provenance lives on the chunk row, so a citation renders from one row with no
  join and cannot drift from the text it points at.

**When to revisit.** Past roughly a million chunks, or when ANN recall on an HNSW
index measurably beats exact search on latency at p95. Neither is close. The
HNSW indexes are already created, so the scaling path is a parameter change.

### Hybrid retrieval with reciprocal rank fusion

Keyword (Postgres FTS) and semantic (pgvector) run independently and are fused by
**rank**, not score. Their scales are not comparable — `ts_rank_cd` is unbounded
and cosine similarity is in [-1, 1] — so any weighted sum of the raw numbers is
arbitrary. RRF needs only the ordering, and a chunk found by both paths
accumulates from both, which is the behaviour we want: agreement between
independent retrievers is evidence.

Keyword search also carries a **trigram fallback** for queries with no indexable
dictionary terms (`n(A)`, `22/7`). Written first with the pg_trgm `%` operator,
which does not survive the driver's parameter escaping — caught by a test, now an
explicit `similarity() > 0.08`.

### Chunking: heading-aware, with a worked solution treated as atomic

Target 180 words, hard maximum 340, minimum 40, split on `##` headings and then
on paragraph boundaries. One rule overrides all of them: **a worked solution is
never split.** Half a method retrieved on its own looks complete and is not — it
is the most dangerous possible output for an exam-prep tool.

"Not on this syllabus" sections are atomic too, for a reason discovered by the
eval suite: at 30–40 words they were below the merge threshold, got folded into
their neighbours, and lost their headings. Grounded refusal finds them by
heading, and was catching 0 of 12 out-of-syllabus questions as a result.

`sabi ingest --dry-run` prints every chunk with its word count and flags, because
bad chunking is the commonest silent cause of bad retrieval and the only defence
is being able to look at it.

### Sibling expansion

A student's question matches the *Question* section of a worked example almost
word for word, and that section contains no method. Indexing Question and
Solution separately keeps the match sharp; expanding to the rest of the document
at context-assembly time keeps the answer complete. Small-to-big retrieval, for a
concrete reason rather than because it is a known pattern.

### Reranking is feature-based, not a cross-encoder

`FeatureReranker` scores idf-weighted term coverage, bigram hits, term density
and heading match. It is not a cross-encoder and does not claim to be.

**Why.** A cross-encoder means either a model download (torch, several hundred MB,
a cold-start cost on a 512MB instance) or an API call on the hot path. The
deterministic reranker costs nothing, runs offline, and is reproducible — which
is what makes the numbers in EVALUATION.md reproducible.

`VoyageReranker` (rerank-2.5-lite) sits behind the same interface for when a key
is configured. Its effect would be *measured* by re-running the suite, not
assumed.

### Confidence is one number, and it multiplies

Four signals: top score, margin over the third result, agreement between the two
retrievers, and support mass. The first version **added** them, which handed out
0.30 before the quality of the best chunk was considered at all — "Explain
photosynthesis" scored 0.37 on a best chunk of 0.12 and got answered. They now
modulate the top score instead of padding it. A bad best chunk cannot be rescued
by agreement about how bad it is.

---

## Embeddings and models

### Local LSA offline, Voyage in production

**Decision.** Two embedders behind one interface. `local_lsa` (TF-IDF reduced by
truncated SVD, pure numpy) is the default; `voyage-3.5-lite` at 256 dimensions is
the production path.

**Why an offline embedder at all.** Everything — retrieval, refusal, caching,
metering, cost accounting, the eval harness, CI — runs with no API key and no
network. Anyone can clone the repo and reproduce every number in EVALUATION.md.
A portfolio piece whose evaluation cannot be re-run is an assertion.

**Cost, stated plainly.** LSA is a genuinely semantic method but a weaker one
than a trained embedding model, and it is **fitted on the corpus**, so a corpus
edit changes every vector and requires `sabi reindex`. Ingest refuses to run if
the stored embedder identity does not match the configured one, rather than
writing vectors that cannot be compared with the ones already there. The
production embedder is stateless and has neither property.

**Why Voyage over OpenAI.** Anthropic does not serve embeddings and recommends
Voyage; using Voyage keeps the stack to two vendors instead of three, and
`voyage-3.5-lite` at 256 dimensions is the cheap end of a model family built for
retrieval. 256 rather than the default 1024 because the index is smaller and the
retrieval difference on 188 chunks is not measurable.

### Model routing: Haiku 4.5 by default, Sonnet 5 on escalation

Escalation happens on low retrieval confidence, or on a structurally complex
question (multi-part, long, or containing "hence" / "show that" — the Paper 2
Section B shape where a cheap model answers part (a) and forgets part (b)).
Budget pressure overrides both. Which model served, and why, is on every request
row.

Haiku 4.5 takes no `effort` parameter, so nothing is sent on the cheap path;
these are short grounded answers, not reasoning problems. Sonnet 5 escalation
runs adaptive thinking at low effort — headroom for a harder question without a
long reasoning pass in front of a student on 3G.

### Refusals are templated, never generated

No model writes a refusal. Three reasons: a refusal must be reliable and a model
is the least reliable component; a refusal should cost nothing, and
out-of-syllabus questions repeat as much as answerable ones; and the wording
shown to a student who might be worried is a product decision, not a sampling
outcome.

---

## Answering

### Citations are validated before anything is shown

Locators are parsed out of the model's output and checked against what was
actually retrieved. An invented one is stripped. If no valid citation survives,
the answer is **discarded** and replaced with a refusal (`refusal_kind =
ungrounded`). It is better to show a student nothing than a claim with a
fabricated source.

The citation pattern (`[EX 31]`, `[SYL A3]`) is deliberately narrow, because
maths notation uses square brackets constantly: `S(n) = (n/2)[2a + (n−1)d]`. The
generator, the eval scorer and the HTML renderer all use the same pattern, so all
three agree on what a citation is. They did not at first, and the scorer reported
five false failures.

### Refusal decision order

Cheapest and most certain first: grounded out-of-scope (cite the line that says
so) → nothing retrieved → confidence below threshold → generate, then validate.

### The welfare guardrail is one rule, before everything

A narrow pattern check that runs before retrieval and before any model call, so
it cannot depend on a model behaving. It does not counsel, does not assess risk,
and does not attempt to be a helpline: it says what Sabi is for and points at a
teacher or a trusted adult. The patterns are narrow and the response is written
so a false positive is harmless. The matched phrase is never logged and never
stored separately — a student who types something painful does not get it filed.

---

## Cost control

### Semantic caching, with a numeric guard

Exam questions repeat heavily across students. A cache hit costs one embedding
call and one vector lookup.

The guard that makes it usable: **an entry only matches when the multiset of
numbers in the question matches exactly.** "Volume of a cone of radius 7" and
"radius 14" are near-identical as text and have different answers. Without this,
semantic caching in a maths product is a machine for confidently returning the
wrong number.

Entries are scoped to corpus version + prompt version + provider + an
**answerer revision** bumped by hand. Prompt version alone does not cover a
change to the answering code, and a cache that outlives the code that filled it
serves answers from a system that no longer exists.

Refusals are cached too.

### The budget kill switch counts product traffic, not eval runs

Below the warn fraction: normal. Past it: cheap model only, no escalation. At the
ceiling: cache-only, and a question with no hit gets an honest "we're at capacity
today" page rather than a quietly degraded answer.

Eval traffic is excluded from the ceiling. A threshold sweep is 25 consecutive
suite runs, and letting development work degrade the student-facing service would
be the wrong failure. Eval spend is still recorded on every request and shown as
its own line in the report, so it cannot hide.

### Estimated cost is flagged, never blended

The offline provider makes no API call, so its rows are priced at the cheap
model's rates purely to exercise the accounting, and flagged `cost_is_estimated`.
The report prints a warning when any row in the window is estimated. A report
that quietly mixes estimated and billed spend is a report that lies.

### Cost per user is computed from active days

`spend per active user-day × observed active days scaled to a month`, rather than
total spend ÷ total users, which flatters the number every time someone signs up
and leaves. Currently **$0.025 per user per month** projected.

---

## Access, identity and limits

### Anonymous by default, with IP as the backstop

A device-scoped random id in a cookie. No account, no phone number, no email
unless volunteered for the waitlist. Anonymous ids are resettable, so the daily
cap alone is trivially evaded; a salted **hash** of the IP is the backstop, never
the address itself.

The IP cap is set deliberately high (90/day against a 15/day user cap). Nigerian
mobile carriers use CGNAT and school computer rooms sit behind one address —
a tight IP cap would punish exactly the students this is for.

### Limits live in the database, seeded from a file

`config/limits.yaml` is hot-reloaded on mtime, and the `plans` table is the
source of truth at request time, so a cap can be changed at 11pm without a
deploy. Every limit is read from the plan; none is a constant in code.

### Day boundaries are West Africa Time

A student at 11pm should see the cap reset at midnight where they are. WAT is
UTC+1 all year with no daylight saving, so a fixed offset is correct and avoids
depending on the tz database being present on the host.

### The eval harness is metered like a user

It runs on an `internal` plan — generous, not unlimited. There is no unmetered
path in the system, including for my own testing.

---

## Monetization

### Paystack, not Stripe — and no checkout in v1

The seam exists: a `plan` on every user, limits read from the plan, a billing-
shaped `usage_events` row per question priced at zero, and a `PaymentProvider`
interface whose only implementation raises `NotImplementedError`.

**Paystack** because Stripe does not properly serve Nigerian merchants —
onboarding a Nigerian entity is the exception rather than the path, settlement in
naira to a Nigerian bank account is the normal case here, and Paystack handles
bank transfer and USSD alongside cards.

No checkout, no pricing page, no naira figure. Pricing should come from what real
students say, not from a number guessed before anyone has used it.

---

## Interface

Full reasoning in `DESIGN_PLAN.md`, written before any code. The decisions with
engineering consequences:

- **No webfonts.** System stack resolves to Roboto on the target device: already
  present, hinted for low-density screens, zero bytes over metered data. A design
  that needs 400KB of font to feel warm has failed this audience. Home page 3.2KB,
  answer page 4.8KB.
- **Server-rendered, works without JavaScript.** The composer is a real form POST
  and source panels are `<details>`. JS only adds a visible working state, an
  in-place down-vote reason, and an honest message on timeout.
- **One accent, one meaning.** Red is a citation, a refusal or a correction —
  never decoration, never a button fill.
- **Contrast is checked in CI** from the real stylesheet (`tools/contrast_check.py`),
  so the claim cannot drift from the CSS.

---

## Things deliberately not done

- **Alembic.** The schema is `create_all` plus a forward-only list of idempotent
  `ALTER`s. That list is a migration system in miniature and saying so is more
  honest than pretending `create_all` is enough — it silently ignores columns
  added to an existing table, which is how the first one got missed. It becomes
  Alembic the day there is production data worth preserving.
- **Streaming answers.** Answers are short and the wait is dominated by retrieval
  plus one model call. Streaming adds a failure mode (a half-written answer with
  half its citations) for little gain at this length.
- **User accounts, history, saved questions.** Every one is more PII about
  minors. None is needed to answer a question.
- **A moderation system.** One guardrail rule, as the brief asks. A classifier
  for a 22-item risk surface would be more code than judgement.
