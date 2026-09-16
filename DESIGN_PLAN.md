# Design plan — Sabi

Written before any application code. Reviewed against the brief's forbidden list at the
bottom, with the changes I made and why.

## What this thing is

A WAEC SS3 Mathematics study assistant that answers from retrieved syllabus text and
past-question solutions, shows the source for every claim, and says "I don't have that"
instead of guessing.

**Name: Sabi.** Nigerian pidgin for knowing a thing properly ("I sabi am"). Four letters,
fast to type on a phone keyboard, student-native rather than product-native. The interface
voice follows from the name: a person who knows the work, not a brand.

## Palette — six values

| Token      | Hex       | Role                                                              |
|------------|-----------|-------------------------------------------------------------------|
| `paper`    | `#FBF9F4` | Page. Warm milk-white, the colour of exam answer-booklet stock.    |
| `rule`     | `#DCD4C4` | Hairlines and the ruled margin. Warm tan, never grey.              |
| `ink`      | `#2E3338` | All body text, headings, structure. Chalk-slate. 12.1:1 on paper.  |
| `ink-soft` | `#565E66` | Secondary text: counts, helper lines. 6.3:1 on paper.              |
| `mark`     | `#8C2F2F` | **Evidence and correction only.** Citations, refusals, down-vote state, the disclosure rule. 7.8:1 on paper. |
| `wash`     | `#F6EAE6` | Fill of an opened source panel — the faintest tint of `mark`, so an opened citation reads as a different *sheet*, not a different *component*. `mark` on `wash` is 7.0:1. |

Contrast ratios above are computed, not estimated (`tools/contrast_check.py`, run in CI).
The milk background never carries grey text below 4.5:1 — `ink-soft` is the lightest text
token that exists, and there is no lighter one to reach for.

**The one rule that governs the accent:** if something is red, it is either a citation, a
refusal, or a correction. Red is never a button fill, never a section divider, never
decoration. A student should be able to learn in one session that red means "this is about
where the answer came from."

## Type — one family, plus mono for locators

1. **Body and headings — system sans stack.**
   `-apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
   On the target device (a cheap Android) this resolves to Roboto: already on the device,
   hinted for low-density screens, and it costs **zero bytes over metered data**. Headings
   are separated from body by weight (600) and size only — same family.
2. **Locators — system mono stack.**
   `ui-monospace, "Roboto Mono", "DejaVu Sans Mono", Consolas, monospace`
   Used *only* for provenance strings: question numbers, years, syllabus section codes,
   chunk ids in the admin view. Mono is the second face because an exam paper's question
   numbering is fixed-width and stamped — it reads as a *locator*, not as prose. It is
   unambiguously distinct from the body face and is not a display serif.

No webfont is downloaded. CSS budget: 8KB. No icon font, no sprite sheet.

## The hero element: a citation

This is the product's entire claim, so it is the most carefully built object on the page and
everything else is deliberately plainer than it.

Closed state — inline in the answer, at the end of the sentence it supports:

```
The sum of the interior angles of a polygon
is (n - 2) x 180 degrees. [2018 Q7b]
                          ^ mono, mark red, underlined with a 1px
                            red rule sitting 2px low — a pen line
                            under the reference, not a hyperlink
```

Open state — the source, rendered as a strip of the paper it came from:

```
|  2018 Q7b                   WAEC · Core Maths
|  --------------------------------------------
|  Calculate the sum of the interior angles
|  of a regular polygon with 12 sides.
|
|  Solution: Sum = (n - 2) x 180
|            ======================
|          = (12 - 2) x 180 = 1800
^
red margin rule, 3px, full height of the panel
```

Three details do the work:

- The **red margin rule** down the left of the panel is the ruled margin of a marked script.
  It is the only 3px element in the product.
- The **matched span is pen-underlined**, not highlighted — a 2px `mark` rule under the exact
  sentence the retriever scored, offset below the baseline so descenders survive. A
  highlighter block would say "search result"; an underline says "a person read this."
- The locator string in the answer and the locator string in the panel header are
  **byte-identical and the same colour**. That is the academic-footnote link made literal.
  Opening a panel flashes its margin rule once, so the eye can find which one moved.

Panels are hairline-ruled and square-cornered (2px radius). No shadow. Paper does not float.

## Wireframe — main answer view, 360px

```
+----------------------------------------+
| Sabi          WAEC Maths      11 left  |  <- cap shown before it is hit
+----------------------------------------+  <- 1px rule
|                                        |
|  Find the sum of the interior angles   |  <- the student's question,
|  of a 12-sided polygon.                |     ink, 17px
|                                        |
|  ------------------------------------  |  <- 1px rule, full bleed
|                                        |
|  Use the formula for the sum of        |  <- answer, 17px/1.6
|  interior angles of a polygon with     |
|  n sides. [2018 Q7b]                   |  <- locator, mono, red
|                                        |
|      Sum = (n - 2) x 180               |  <- display maths, centred,
|          = (12 - 2) x 180              |     mono, ink
|          = 1800 degrees                |
|                                        |
|  +----------------------------------+  |
|  |# 2018 Q7b           WAEC · Core  |  |  <- source panel, collapsed
|  |# Show the source                 |  |     by default on mobile
|  +----------------------------------+  |
|                                        |
|  +----------------------------------+  |
|  |# SYL 3.2      Mensuration        |  |
|  |# Show the source                 |  |
|  +----------------------------------+  |
|                                        |
|  Was this right?    [ Yes ]  [ No ]    |  <- plain words, not icons
|                                        |
|  ------------------------------------  |
|  # Sabi can be wrong. Check with your  |  <- red hairline at left,
|  # teacher or the WAEC syllabus        |     ink-soft text, always on
|  # before you trust it in an exam.     |     the answer surface
|                                        |
+----------------------------------------+
|  Ask another question...          [>]  |  <- sticky composer
+----------------------------------------+
```

Refusal state replaces the answer body, same page furniture:

```
|  I do not have material on this.       |  <- ink, same size as an answer
|                                        |
|  # What I have is WAEC Core Maths for  |  <- red margin rule: this is a
|  # SS3. Matrices and determinants are  |     correction, so it is red
|  # on the Further Maths syllabus, not  |
|  # this one.                           |
|                                        |
|  Try searching: "transformation of     |
|  the plane", "vectors"                 |
```

The refusal names what *is* covered and gives two real next searches. It never implies the
question was a bad one.

## Principles that make this specific to this product

1. **Paper, not chrome.** Separation comes from hairline rules and whitespace, the way a
   ruled answer booklet separates things. Nothing floats, nothing has a shadow, nothing is
   pill-shaped.
2. **Red is evidence.** One accent, one meaning, enforced in review.
3. **The citation out-designs everything else.** If a student remembers one visual thing
   about Sabi, it must be the opened source panel.
4. **Bytes are a design constraint.** No webfonts, no framework, server-rendered HTML, ~30KB
   first load. On 3G the first paint must not wait on a round trip for type. A design that
   needs 400KB of font to feel warm has failed this audience.
5. **Motion only where something changed.** Two animations exist: the source panel opening,
   and the answer text arriving. Both are suppressed under `prefers-reduced-motion`.
6. **The limit is stated before it bites.** The remaining-questions count sits in the header
   from the first question, not in a modal at question 15.

## Review against the brief's forbidden list — what I changed

I drafted this once, checked it against the list, and changed six things:

| First draft | Why it was wrong | Now |
|---|---|---|
| Source Serif for headings, "textbook" feel | High-contrast display serif on cream is exactly the AI-generated signature the brief names | One sans family; headings differ by weight and size only |
| A warm clay secondary accent on the composer button | The `#D97757` family, explicitly forbidden — and it would have given red a rival | Composer button is `ink`; red stays evidence-only |
| Past questions as rounded cards with a soft grey shadow | Identical rounded cards with the same shadow, and shadows contradict the paper metaphor | Hairline-ruled strips with a red margin rule, 2px radius, no shadow |
| `ASK · CITE · CHECK` eyebrow above the landing headline | Tracked-out caps eyebrow *and* a middle-dot meta string, both forbidden | Removed entirely; the headline carries it |
| "See source →" | Arrow appended to link text | "Show the source" |
| Fade-and-slide-up on each landing section | Decorative motion on content that had not changed | Removed; the motion budget is spent on disclosure and streaming only |

One numbering pattern survives on purpose: the steps inside a worked solution are numbered,
because a worked solution genuinely is a sequence. There is no `01 / 02 / 03` anywhere else.

## Accessibility commitments

- Visible focus: 2px `mark` outline with 2px offset on every interactive element. Never
  `outline: none`.
- Touch targets at least 44px. The citation disclosure is a full-width button, not a small
  chevron.
- `prefers-reduced-motion: reduce` disables the panel transition and renders answers in one
  paint instead of streaming.
- The disclosure line is real text in the answer region, read by a screen reader immediately
  after the answer — not a visually-hidden footer.
- Works with JavaScript off: the composer is a real `<form>` POST and source panels are
  `<details>` elements. JS only upgrades to streaming and inline expansion.
