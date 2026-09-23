# Locators — the citation scheme

A **locator** is the short marker a student sees in an answer (`[EX 31]`) and
in the header of the source panel it opens. It is the visible end of the
product's central claim, so it is specified rather than improvised.

Contract between: the corpus, `sabi/answer/generator.py` (validation), the
renderer, and `evalharness/scorers.py` (scoring). **Frozen in Phase 0** —
changing it goes through the lead.

---

## 1. What exists today (measured, not remembered)

Every locator in the 170-document corpus has one of exactly two shapes:

| Shape | Count | Example | Meaning |
|---|---|---|---|
| `<PREFIX> <n>` | 96 | `EX 31`, `PEX 1`, `CEX 8` | Worked example number *n* |
| `<PREFIX> <L><n>` | 74 | `SYL A1`, `PHY C3`, `CHM B1` | Syllabus section *L n* |

Prefixes in use: `EX` (Maths examples), `SYL` (Maths syllabus), `PEX`/`PHY`
(Physics), `CEX`/`CHM` (Chemistry).

The regex is:

```python
r"\[([A-Z]{2,3}\s?[A-Z]?\d{1,3}(?:\.\d+)?)\]"
```

### Two findings from the audit

1. **The `(?:\.\d+)?` branch is dead.** No locator in the corpus uses a decimal
   suffix. It is unused headroom, which is convenient — it means widening the
   pattern breaks nothing that exists.
2. **The regex is copied five times, in three variants**, and nothing keeps
   them in step:

   | File | Form |
   |---|---|
   | `sabi/answer/generator.py:35` | unanchored, for extraction |
   | `sabi/api/render.py:19` | unanchored, for rendering |
   | `evalharness/scorers.py:104` | unanchored, for scoring |
   | `tests/test_physics_corpus.py:35` | **anchored**, for validation |
   | `tests/test_chemistry_corpus.py:36` | **anchored**, for validation |

   If one is widened and the others are not, a locator validates in the corpus
   test and is then silently stripped from the answer — the exact class of
   failure v1 built citation validation to prevent. **This must become one
   constant in one module that all five import** (Phase 1, agent B).

---

## 2. The scheme

### 2.1 Existing locators do not change

170 documents, 157 golden items and a committed eval baseline reference them.
Renaming `EX 31` to `MTHX 31` would buy cosmetic consistency and cost a corpus
rewrite, a golden-set rewrite and a baseline regeneration. Not worth it.

**Rule: the scheme extends; it does not renumber.**

### 2.2 New subject content

| Kind | Form | Example |
|---|---|---|
| Syllabus / curriculum note | `<SUB> <Section><n>` | `BIO A1`, `ECO C2`, `LIT B4` |
| Worked example | `<SUB>X <n>` | `BIOX 4`, `ECOX 12` |

`<SUB>` is a 2–3 letter subject code, registered in
`contracts/subject_codes.yaml` (one file, so two subjects cannot collide).
Physics and Chemistry keep their existing `PHY`/`PEX` and `CHM`/`CEX` rather
than moving to `PHYX`/`CHMX`.

### 2.3 Past questions — the new shape

```
<BODY> <year>.<paper>.<question>
```

| Example | Reads as |
|---|---|
| `WAEC 2019.2.7` | WAEC 2019, Paper 2, Question 7 |
| `JAMB 2021.1.45` | JAMB 2021, Paper 1, Question 45 |
| `NECO 2020.1.12` | NECO 2020, Paper 1, Question 12 |

The **marker stays short on purpose.** v1 learned that citation markers in
prose are scored as content: moving a marker from its own line to the end of
the sentence it supports dropped the fully-grounded rate from 0.82 to 0.56
without changing a single answer, because the marker's tokens appear nowhere in
the source it points at. Scorers now strip markers before grading, and a long
marker would still cost prose readability.

**The full provenance lives in the source panel, not the marker.** The panel
already renders title, attribution and body from the chunk; for a past question
it shows "WAEC 2019 · Paper 2 · Question 7" spelled out, plus the licence
status. The marker is the key; the panel is the meaning.

### 2.4 The widened regex

```python
CITATION = re.compile(r"\[([A-Z]{2,4}\s?[A-Z]?\d{1,4}(?:[.\-]\d{1,3}){0,2})\]")
```

Changes: prefix `{2,3}` → `{2,4}` (for `WAEC`, `JAMB`, `BIOX`); number
`{1,3}` → `{1,4}` (for a four-digit year); the dead `(?:\.\d+)?` becomes
`(?:[.\-]\d{1,3}){0,2}` (for `.paper.question`).

Verified against every existing shape and the new ones:

| Locator | Matches |
|---|---|
| `EX 31` | ✓ |
| `SYL A1` | ✓ |
| `PEX 1`, `CEX 8`, `CHM B1`, `PHY A1` | ✓ |
| `BIOX 4`, `ECO C2` | ✓ |
| `WAEC 2019.2.7`, `JAMB 2021.1.45` | ✓ |

**It still does not match mathematics notation**, which is the property that
matters most. v1's first attempt matched any `[...]` and reported five false
failures because a worked solution legitimately contains
`S(n) = (n/2) times [2a + (n - 1)d]` and `x = [7 plus or minus 5]`. The
ALLCAPS-then-digits shape is what excludes those, and widening the letter and
digit counts does not weaken it: `[2a + (n - 1)d]` has no leading capitals,
`[7 plus or minus 5]` has lowercase words.

---

## 3. Changing this is one commit

The regex, the validator, the renderer, the scorers and the corpus tests move
**together, in a single commit**, and the commit must include:

1. A re-run of the eval showing **`citations.validity` is still 1.000.** That
   metric has zero tolerance in `GATED` and it is the product's central claim.
2. A test asserting every locator in the corpus matches the anchored form.
3. A test asserting the constant is imported, not re-declared — so the five
   copies cannot come back.

A locator that validates in the corpus but fails extraction is invisible: the
answer renders, the citation is silently stripped, and the student sees an
uncited claim. That is the failure mode this document exists to prevent.
