# Sabi — design plan

Written before the redesign, and reviewed against itself before any CSS was
written. It replaces the first design plan entirely: that one argued for paper,
system fonts and near-zero motion, and this one argues for indigo cloth, two
webfonts and one orchestrated moment. The reasons for the reversal are in
[What changed, and why](#what-changed-and-why).

One thing carries over unchanged, because it was right: **the citation is the
product**, so it is the most carefully built object on the page and it is what
the landing page opens with.

---

## The brief

| | |
|---|---|
| Product | A study assistant for Nigerian secondary-school exams (WAEC and NECO) that answers from retrieved syllabus text and worked examples, shows the source for every claim, and refuses when retrieval does not support an answer. |
| Audience | SS3 students, 16–17, weeks from a paper that gates university entry. Mostly on cheap Android handsets over metered mobile data. Their teachers and parents look over their shoulders. |
| The landing page's job | Convince a student in about ten seconds that this will not lie to them, and get them to ask one question. |
| The fear it answers | Being handed a confident, plausible, wrong answer two weeks before the exam. That is worse than no answer. |

---

## Colour — adire indigo

The palette comes from **adire eleko**, the Yoruba indigo resist-dyed cloth: the
cloth is dipped repeatedly, and each dip takes it a step deeper, so a tonal
indigo scale is a real material fact rather than a generated ramp. Undyed cotton
shows through where the cassava paste resisted the dye, and that is the content
surface.

| Token | Hex | On paper it is | Role |
|---|---|---|---|
| `indigo-9` | `#0A1230` | the eighth dip | deepest ground; the hero |
| `indigo-8` | `#101A3C` | the sixth dip | dark sections, the nav |
| `indigo-7` | `#182654` | the fifth dip | a raised surface on dark |
| `indigo-5` | `#26386F` | the third dip | borders on dark, pressed states |
| `indigo-3` | `#4A5F9E` | the second dip | the adire pattern itself |
| `indigo-2` | `#7A8CC0` | the first dip | muted text on dark |
| `cotton` | `#F7F3EA` | undyed cloth | the page; and text on indigo |
| `cotton-2` | `#EDE7DA` | cloth, shaded | an opened source panel |
| `cotton-3` | `#DDD4C2` | cloth, folded | hairlines on paper |
| `ink` | `#111A38` | — | body text on paper |
| `ink-soft` | `#4C5675` | — | secondary text on paper |
| `saffron` | `#E5A72C` | — | **evidence**, on dark only |
| `bronze` | `#8A5A0B` | — | **evidence**, on paper |

**The rule that governs the accent, kept from the first plan because it earned
its place:** if something is saffron or bronze, it is a citation, a refusal or a
correction. It is never a section divider and never decoration. A student should
be able to learn in one session that this colour means *this is about where the
answer came from*.

Saffron cannot be text on cotton — it lands at 1.9:1 — so evidence on a light
surface is bronze instead. That is why there are two accent tokens rather than
one, and it is a contrast requirement, not a palette flourish.

Every pair below is computed from the stylesheet by `tools/contrast_check.py`,
which fails CI if any of them drops under 4.5:1. The large-text 3:1 allowance is
refused throughout: a student reading a worked solution on a bright bus is not
reading large text.

```
cotton       on indigo-9    16.60      ink        on cotton      15.43
cotton       on indigo-8    15.35      ink-soft   on cotton       6.55
cotton       on indigo-7    13.13      bronze     on cotton       5.34
indigo-2     on indigo-8     5.13      bronze     on cotton-2     4.80
saffron      on indigo-8     8.01      ink        on cotton-2    13.87
saffron      on indigo-9     8.66      cotton     on bronze       5.34
```

---

## Type

Two families, clearly distinct — a soft serif against a geometric sans.

**Fraunces** for display only: the wordmark, the landing headlines, the section
openers, and the one number on the dashboard worth looking at. It has genuine
calligraphic stroke modulation without being a script, and an **optical size
axis** (`opsz` 9–144) that is the reason it is here: set at 144 a headline gets
fine, high-contrast detail, and the same file set at 9 keeps a small heading
sturdy. One file, 67 KB, weights 400–700.

**Outfit** for everything a student actually reads or operates: body copy, nav,
buttons, form fields, tables. Weights 300–700 from one 32 KB file.

Both are self-hosted, latin subset, `font-display: swap`, and preloaded. Total
**99.6 KB** for every weight in the product.

*Recorded tradeoff:* Fraunces also has `SOFT` and `WONK` axes, which are what
give it its quirk. Google only serves those via the TrueType path, and this app
has no compression middleware in front of `StaticFiles`, so taking them would
mean serving uncompressed TTF. `opsz` is the axis that earns its bytes on a
display face; the other two are skipped and noted here rather than discovered
later.

A **system monospace** stack survives for exactly one thing: locators
(`SYL A1`, `EX 14`). An exam paper's numbering is fixed-width and stamped — it
reads as a *reference code*, the way an ISBN does, so the mono is encoding
information rather than decorating a label. It appears nowhere else, and in
particular not on small UI labels.

### Scale

A modular scale, not a list of decimals. `--step--1` through `--step-6`, ratio
1.2 on mobile widening to 1.25 above 600px, expressed with `clamp()` so the
headline scales with the viewport instead of jumping at a breakpoint. Body text
is 17px at 360px. Line length is capped at 68 characters; the serif gets more
line-height than the sans.

---

## Layout

The hero does not describe the product. **It is the product**: a real question,
already answered, with its source panel open and the cited sentence underlined —
the thing the whole system exists to do, working, above the fold. Nothing a
headline could claim is as convincing as the artifact itself.

```
 360px                              1024px
┌────────────────────┐   ┌──────────────────────────────────────────┐
│▚ indigo, adire ▚▚▚ │   │▚▚ indigo ground, adire resist pattern ▚▚ │
│                    │   │                                          │
│ Sabi     Log in    │   │ Sabi          How it works   Log in  ▣   │
│ ────────────────── │   │ ──────────────────────────────────────── │
│                    │   │                                          │
│ Show your          │   │ Show your           ┌──────────────────┐ │
│ working.           │   │ working.            │ Solve 2x²+5x−3=0 │ │
│  ↑ Fraunces 700    │   │                     │ ──────────────── │ │
│    opsz 144        │   │ Every maths teacher │ 1. Factorise...  │ │
│                    │   │ asks you to. Sabi   │ 2. ...  [EX 29]  │ │
│ Every maths        │   │ holds itself to it. │                  │ │
│ teacher asks you   │   │                     │ ┃ SYL B3         │ │
│ to. Sabi holds     │   │ ┌─────────────┐     │ ┃ Solve quadratic│ │
│ itself to it.      │   │ │ Ask a       │     │ ┃ equations by   │ │
│                    │   │ │ question    │     │ ┃ completing the │ │
│ ┌────────────────┐ │   │ └─────────────┘     │ ┃ square...      │ │
│ │ Ask a question │ │   │                     │ ↑ saffron margin │ │
│ └────────────────┘ │   │ 15 free a day.      │   rule, the open │ │
│                    │   │ No card.            │   source         │ │
│ ┌────────────────┐ │   └─────────────────────┴──────────────────┘ │
│ │ Solve 2x²+5x−3 │ │                                              │
│ │ ────────────── │ │   ← asymmetric: text 5 cols, artifact 7,     │
│ │ 1. Factorise.. │ │     artifact bleeds past the container edge  │
│ │ 2. ..  [EX 29] │ │                                              │
│ │ ┃ SYL B3       │ │
│ │ ┃ Solve quad.. │ │   Mobile is not the desktop layout shrunk:
│ └────────────────┘ │   the artifact moves below the CTA, the
│                    │   pattern loses two of its four motifs, and
└────────────────────┘   the nav collapses to wordmark + one action.
```

**Alignment is left, throughout.** A centred hero column is the default that
every generated landing page arrives at; left-aligned text against an
off-centre artifact gives the page a spine and lets the artifact overhang it.

Below the hero: how it works as a genuine four-step sequence (ask → retrieve →
cite → refuse if unsure), which is the one place numbering is legitimate because
the content really is ordered. Then subjects. Then the honest limits. Then FAQ
as `<details>`. Then footer.

Structure comes from the cloth: a **hairline and a change of ground**, not a
grid of identical cards. Radii differ by role — 4px on inputs and buttons, 10px
on the answer artifact, 0 on full-bleed bands — so radius encodes hierarchy
instead of being applied uniformly.

### The adire pattern

Four motifs drawn as one tiling inline SVG on the indigo ground, in `indigo-3`
at low opacity: bundled parallel lines, concentric rings, a dotted grid, and
small crosses. They are stroke-drawn with slight irregularity, because resisted
cloth is hand-drawn and a machine-perfect repeat would read as wallpaper. It is
**ground, never ornament on content** — it never sits behind body text.

---

## Motion

One orchestrated moment: on load, the hero headline, lede and artifact arrive in
a short staggered sequence, and the source panel's margin rule draws itself once
so the eye lands on the thing that matters. That is the whole of the
non-interactive motion budget.

Everything else answers an action — opening a source, switching between log in
and sign up, expanding an FAQ row, saving to the notebook. All of it is
suppressed under `prefers-reduced-motion: reduce`, where the hero renders in one
paint.

No scroll-triggered fade-and-slide on each section. That is the generic default,
and it also means a student on a slow connection watches content arrive twice.

---

## Principles

1. **The citation is the hero, literally.** The first thing on the page is a real
   answer showing its source. If a student remembers one visual thing about
   Sabi, it must be the opened source panel.
2. **Indigo is the ground, cotton is the content, saffron is only ever
   evidence.** One accent, one meaning, enforced in review and in CI.
3. **Pattern, not decoration.** The motifs come from the audience's own material
   culture, and they stay behind the content rather than on it.
4. **Bytes are still a design constraint**, but the budget is now spent
   deliberately: 99.6 KB of webfont, measured by a test, on a page that used to
   spend zero. A design that needs 400 KB of font to feel warm has still failed
   this audience.
5. **Motion once.** One page-load sequence; after that, motion only shows what
   changed.
6. **The limit is stated before it bites.** The daily allowance is visible from
   the first question, not in a modal at the fifteenth.

---

## Reviewed against the brief

The `frontend-design` skill lists the traits that current AI-generated design
clusters around. Working through them against a first draft of this plan caught
two real problems and confirmed several deliberate choices.

| Draft | Why it was wrong | What replaced it |
|---|---|---|
| **Warm paper `#FBF9F4`, a high-contrast serif display, and a terracotta accent.** This was the first proposal and it was approved before review. | It is named, exactly, as the single commonest tell — and the terracotta family sits on `#D97757`, which is Claude's own interaction accent, so on this brief it reads as a signature rather than a choice. It was also roughly what the product already looked like. | Adire indigo and saffron, taken from the audience's material culture. The serif stays, because the brief pinned it. |
| A near-black ground with one bright accent. | The second named tell. | The ground is unmistakably *blue* — a three-step indigo scale with a material reason for each step, not a tinted black. |
| `ASK · CITE · CHECK` as a tracked-out caps eyebrow over the headline. | Caps eyebrow and middle-dot meta string, both named tells, and it said nothing the headline did not. | Cut. The headline carries it. |
| Feature set as six identical rounded cards with the same soft shadow. | The SaaS-card kit, named. Uniform radius also throws away hierarchy. | Bands of changing ground, hairlines, and one genuinely raised object — the answer artifact. Radius varies by role. |
| `Start free →` as the primary button. | An arrow appended to button text, named; and "start free" does not say what happens. | `Ask a question`, which is exactly what the button does. |
| One word of the headline in saffron. | Accenting a single word in a headline is named, and it would have given evidence-colour a second meaning. | The headline is one colour. Saffron stays evidence. |
| `01 / 02 / 03` markers on the feature sections. | Only legitimate when the content is a sequence. | Numbers kept **only** on "how it works", which is genuinely ordered. Nowhere else. |
| Scroll-triggered fade-and-slide per section. | Named as the generic default. | One hero sequence, then motion only on interaction. |

Two choices survived review that resemble defaults, and are kept for stated
reasons rather than by omission:

- **A serif display face on a study product.** The brief specified a
  calligraphic-leaning title face by name. The skill is explicit that the
  brief's own words win.
- **A monospace face for locators.** Mono for small labels is named as template
  chrome. Here it marks a fixed-width reference code and appears nowhere else,
  so it is carrying information. If it ever appears on a label that is not a
  locator, it has become decoration and should be removed.

---

## Accessibility

- Focus is visible on **every** interactive element: a 2px saffron ring on dark,
  bronze on paper, with a 2px offset. Never `outline: none`.
- Touch targets are at least 44px. The source disclosure is a full-width
  button, not a small chevron.
- `prefers-reduced-motion: reduce` disables the hero sequence and the panel
  transition, and renders answers in one paint.
- `prefers-contrast: more` thickens hairlines and drops the pattern.
- The disclosure line is real text in the answer region, read by a screen reader
  straight after the answer — not a visually-hidden footer.
- Both themes are checked: the stylesheet declares a dark theme and
  `tools/contrast_check.py` verifies the pairs in both.
- Every page works with JavaScript off. The composer is a real form POST, source
  panels are `<details>`, the FAQ is `<details>`, and log in / sign up are two
  real forms on one page.

## What changed, and why

The first design plan was written for a prototype whose job was to prove that
grounded answering worked and could be measured. Paper, system fonts and almost
no motion were right for that: the argument was the measurement, and the
interface only had to stay out of the way.

The job has changed. This is now a product a student has to choose, on a phone,
against alternatives that will happily guess. A first impression is part of
whether the careful part ever gets used. So the budget moves: two webfonts and
one orchestrated moment, paid for out of a measured budget rather than an
unmeasured one, and every claim about contrast still checked from the real
stylesheet in CI.

What has not changed is what the design is *for*. The citation is still the
hero. The accent still means evidence and nothing else. The limit is still
stated before it bites. And the page still works with JavaScript off, on a cheap
handset, over metered data.
