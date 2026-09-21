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

- **Two self-hosted webfonts**, reversing the original "no webfonts" position.
  The first design was for a prototype whose job was to prove the measurement;
  the interface only had to stay out of the way. This is now a product a student
  has to choose, on a phone, against alternatives that will happily guess, and a
  first impression decides whether the careful part is ever used. Fraunces and
  Outfit, latin subset, variable, **99.6 KB for every weight in the product**,
  self-hosted rather than from a font CDN — no extra DNS and TLS on a slow
  connection, and no third party on a page a 16-year-old loads. The budget moved
  rather than disappearing: `tests/test_assets.py` now measures fonts, CSS and
  JS, none of which any test measured before.
- **The palette is adire indigo**, not the original warm paper and red. The first
  proposal for the redesign was cream, a high-contrast serif and a terracotta
  accent, which is precisely the commonest tell of a generated page — and the
  terracotta family sits on Claude's own interaction accent. Reasoning and the
  full self-critique are in `DESIGN_PLAN.md`.
- **Server-rendered, works without JavaScript.** The composer is a real form POST
  and source panels are `<details>`. JS only adds a visible working state, an
  in-place down-vote reason, and an honest message on timeout.
- **One accent, one meaning.** Saffron on dark, bronze on paper: a citation, a
  refusal or a correction. Never decoration. Two tokens rather than one because
  saffron on cotton is 1.9:1 — a contrast requirement, not a flourish.
- **Contrast is checked in CI** from the real stylesheet (`tools/contrast_check.py`),
  now in **both themes**, and the checker also fails on any colour literal
  outside the token block. That second check is the one that keeps a system a
  system: a ratio table can only vouch for colours it knows the names of.
- **Sessions are rows, not signed cookies.** A new table costs nothing under
  `create_all`, every route already holds a database session, and revocation
  becomes possible. Passwords are `hashlib.scrypt` from the standard library
  with the parameters stored inside the hash — no new dependency, and they can
  be raised later without invalidating anyone.

---

## Switching a third subject on

- **A subject is not on until it is measured.** Chemistry's 39 documents sat in
  the corpus, verified, for a whole phase before being enabled, because
  enabling one changes every vector — the local embedder is fitted on the
  corpus — and invalidates thresholds swept against the old geometry. The order
  was: enable, measure the effect on the subjects already live, author a golden
  slice, re-sweep, regenerate the baseline.
- **Adding Chemistry improved Mathematics.** recall@k went 0.9899 → 1.0000 and
  the long-standing `g-008` miss disappeared. Retrieval is scoped, so no
  Chemistry chunk can ever be returned for a Maths question; the only channel
  is the shared embedder refit re-weighting every term over a corpus 40%
  larger. Worth stating plainly because it is a property of the *offline*
  embedder and cuts both ways — a stateless production model would not move at
  all, and the next refit could just as easily move something the wrong way.
  That is what the per-subject gate is for.
- **Fusion may not discard a retriever's best guess.** Reciprocal rank fusion
  with `k = 60` over 24-item lists gives every rank a score between 1/61 and
  1/84, so appearing in *both* lists outweighs being ranked first in one. That
  is backwards for the case two retrievers exist to cover. "Express a 0.5
  mol/dm³ solution of H2SO4 in g/dm³" is answered word for word by one worked
  example; lexical missed it (the student wrote "change", the document says
  "convert"), the vector search ranked it first, fusion put it twelfth, and the
  student got a confident explanation of average rate of reaction. Each
  retriever's top two now survive into the rerank shortlist regardless.
- **Exclusion sections are evidence for refusing, not material for answering.**
  A "Not on this syllabus" chunk reaching answer context produced exactly what
  it sounds like: "what does a negative index mean?" answered with a list of
  Further Maths topics that are not examined. The refusal path already queries
  those chunks separately, with its own threshold, so nothing else needed them.
  Filtered in Python rather than SQL on purpose — `AND NOT c.is_exclusion` on
  the vector query would put a predicate on the ANN walk its partial index does
  not cover, and the walk would quietly return fewer rows than `LIMIT` asked
  for, which is the exact failure the per-scope indexes exist to prevent.
- **Per-subject recall is gated, and that is arithmetic.** Chemistry is 21 of
  120 answerable items, so its recall could fall from 1.00 to 0.90 and move the
  global figure by 0.0175 — inside the 0.02 global tolerance. The gate
  discovers subjects from the run rather than listing them, so the next subject
  is covered from its first baseline.

---

## Practice

- **Not called a mock exam, and it never will be.** A mock exam implies past
  papers under licence and a mark scheme somebody else wrote. This is questions
  generated from the worked examples already in the corpus. Calling it what it
  is costs nothing and keeps an unsupportable claim out of the product.
- **The numbers are resampled; the shapes are authored.** Asking the 50 worked
  examples directly would not work: they *are* the answer corpus, so a student
  can paste the question into the composer and be handed the worked solution,
  and they overlap the golden eval items, so using them as practice would turn
  the evaluation into a memorisation test. 50 templates sample fresh numbers
  and **compute the answer in Python** — the same rule the Physics and
  Chemistry generators follow, and the only reason to trust any of them.
- **Sampling is constrained next to the arithmetic it protects.** Several
  templates would otherwise produce answers that are correct and useless: a
  parallel resistance of 12/7 ohms, a transformer secondary of 36.67 V, a mean
  printed as 1837/40 when the question asked for two decimal places. One
  produced something worse — a machine more than 100 per cent efficient, which
  is arithmetically consistent and physically impossible. Each constraint is
  written where the working is, because the two go wrong together.
- **One notion of whether two answers are the same number.** `normalise_value`
  moved out of `evalharness/scorers.py` into `sabi/valuematch.py` and the
  harness imports it. Two implementations would have drifted, one of them
  deciding `1/2` and `0.5` are the same answer and the other not.
- **Marking uses the rule a human marker uses**, stated explicitly: a value is
  accepted if it equals the true value correctly rounded to the precision the
  student actually wrote. So `0.33` passes for one third and `1795` does not
  pass for 1800, and nobody had to pick a tolerance. A whole number written
  without a decimal point is treated as a claim of exactness — without that,
  the significant-figure test reads `12` as two figures and accepts it for
  12.4, which is the one direction this must never be wrong in.
- **Nothing is marked until the set is closed.** Marking each answer as it
  arrives turns a timed set into a guessing game against the marker: type, see
  red, try again. A closed set then stops accepting answers, or the score only
  measures how long somebody kept typing.
- **A wrong answer ends at a citation**, not at generated prose — every item
  carries the `doc_id` and locator of the worked example its template came
  from. Same rule as the answer path.
- **Weak topics are a rolling correct-rate, not a mastery model.** A proportion
  over a subtopic's recent answers, with a floor of four answers before
  anything is called weak. It is explainable to a sixteen-year-old in one
  sentence, which matters more here than anything a latent-trait model buys.
- **Practice is not metered against the daily question cap**, because it makes
  no model call and costs nothing to sit — charging a student a question for it
  would be charging for arithmetic. It is capped at 40 sets a day anyway:
  unmetered is not the same as unbounded, and nothing else here would notice a
  client looping on it.
- **`practice_attempts` was not built.** The plan listed it beside
  `practice_sets`, assuming a set is a fixed paper several students could sit.
  Every set is sampled fresh for one student, so a set and an attempt at it are
  the same row and the second table would always hold exactly one row per
  first.
- **Colour is never the only carrier of a mark.** Right and wrong get their own
  tokens, checked against body-text contrast in both themes rather than the
  3:1 a decorative accent would get away with — and neither appears without a
  word beside it saying the same thing, because roughly one student in twelve
  cannot tell those two hues apart.

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
- ~~**User accounts, history, saved questions.**~~ **Reversed.** The original
  reasoning — every one is more PII about minors, and none is needed to answer a
  question — is still true of the *first* clause and still shapes the result:
  asking without an account works, is the default, and stays. What changed is
  that a student revising over weeks has a real use for their own history, and
  refusing them one to keep a slogan would be putting the slogan first. So:
  accounts are optional, hold an address and a scrypt hash and nothing else, and
  signing up claims the identity already on the device rather than creating a
  second one. `privacy.html` and its test were rewritten in the same change,
  because two of the things that page promised had become false.
- **A moderation system.** One guardrail rule, as the brief asks. A classifier
  for a 22-item risk surface would be more code than judgement.
- **A password-reset email.** There is no email transport here, and a reset link
  that reports success and delivers nothing is the most damaging kind of
  working-looking feature. Five one-time recovery codes instead, shown once at
  signup and hashed the way a password is. The sending interface exists in
  `sabi/accounts/mail.py` and raises rather than pretending.
