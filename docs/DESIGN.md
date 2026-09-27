# Sabi — design system: Adire

The brief every screen is built against. The tokens themselves are the frozen
contract in `web/styles/tokens.css`; this file says how to use them. When this
file and `DESIGN_PLAN.md` disagree, this file wins (that plan describes the v1
Jinja landing and is kept as history).

## Design read

> A consumer exam-prep app for Nigerian SS1–SS3 students on cheap Android
> phones, whose parents pay. Confident, fast and calm; premium but never
> flashy; recognisably Nigerian without flag clichés.
>
> Dials (design-taste-frontend): **landing** VARIANCE 7 · MOTION 6 · DENSITY 4.
> **App** VARIANCE 4 · MOTION 4 · DENSITY 5. **Exam mode** VARIANCE 2 ·
> MOTION 1 · DENSITY 6.

## Identity

- **Colour.** Adire indigo is the ground (hero, dark bands, the nav), cool
  undyed cotton is the page, saffron is the one accent. Saffron on indigo,
  bronze (`--gold-text`) on cotton: saffron on a light ground fails contrast.
  **Saffron/bronze means evidence or achievement** (a citation, a locator, a
  measured number, a finished set) and the primary action on indigo. It is
  never decoration or a divider.
- **Meaning is fixed and never colour alone.** Right = `--success` plus the
  word "Correct" and an icon. Wrong = `--danger` plus "Wrong" and an icon.
  Answered / unanswered / flagged in the exam grid each have a symbol *and* a
  word.
- **Type.** Cabinet Grotesk 800/700 (`--font-display`) for headlines and big
  numbers that are not tabular. Satoshi 400/500/700 (`--font-sans`) for all
  reading and UI. Timers, scores and counts: Satoshi with `.tabular`, because
  Cabinet Grotesk has no tabular figures. The mono stack is for locators
  (`SYL B3`) only. No other fonts.
- **Headlines** are left-aligned, tight (-0.03em), 1–2 lines. Emphasis inside a
  headline is weight or saffron-on-indigo *underline*, never a second family.
- **Scale.** `--step--1` … `--step-6`. Body 17px floor; question text
  `--step-1` minimum.
- **Space.** `--s-1` … `--s-9`. **Radius** by role, and only these:
  `--r-control` 6px (buttons, inputs, chips), `--r-panel` 12px (cards,
  sheets, the answer artifact), `--r-pill` (status tags, the tab marker is a
  panel). Full-bleed bands are square.
- **Icons.** Phosphor (`@phosphor-icons/react`; in server components import
  from `@phosphor-icons/react/dist/ssr`). `regular` weight at rest, `fill` for
  the active/selected state. Subject marks and illustrations use
  `components/glyph.tsx` (drawn in the adire stroke) — they are brand art,
  not UI icons. No emoji.
- **The cloth.** `components/cloth.tsx` gives the adire resist pattern
  (`<Adire />`) and the dyed edge between bands. Pattern is ground, never
  behind body text.

## Anti-patterns (refuse these)

Cream paper + serif display; purple/blue glow gradients; glassmorphism; three
identical feature cards with icons; a small uppercase eyebrow over every
section (max one per three sections); centred hero; `Start free →` arrows on
buttons; two CTAs with the same intent and different labels; em dashes in
product copy where a full stop or comma works; "Jane Doe" fake data or fake
testimonials; fake urgency, streak-loss guilt, countdown offers (these are
children). Placeholder art is labelled as a placeholder.

## Motion

**CSS first.** Transitions and keyframes run off the main thread and survive a
busy page on a cheap phone. Motion (`motion`) is for what CSS cannot do well:
interruptible springs, gestures, exit animations of unmounting React trees,
number count-ups.

- **Vocabulary** — use only these. CSS: `--t-tap 100ms`, `--t-fast 180ms`,
  `--t-mid 280ms`, `--t-slow 420ms`, `--t-deal 560ms`; `--ease` (arrivals),
  `--ease-settle` (a little overshoot, physical objects only, never text),
  `--ease-exit` (leaving), `--ease-ink` (page-level). JS: `web/lib/motion.ts`
  (`EASE`, `DUR`, `SPRING`, `STAGGER`, `rise`) mirrors them.
- **Only `transform` and `opacity`** (plus `filter: blur()` ≤ 4px to hide a
  crossfade seam, and `clip-path` for reveals). Never animate layout
  properties. Never `transition: all`.
- **Never from `scale(0)`**; start at 0.95 with opacity 0. Popovers scale from
  their trigger; modals from centre.
- **Press feedback** on everything pressable: `scale(0.97)` on `:active`,
  100 ms. Hover effects only inside `@media (hover: hover) and (pointer: fine)`.
- **Exit faster than enter.** Stagger siblings by 30–60 ms, never blocking a
  tap.
- **Frequency decides.** Things seen 100×/day (keyboard actions, option
  selection in exam mode, grid jumps) do not animate. Occasional things (a
  sheet, a toast, the next practice question) animate briefly. Rare things
  (finishing a set, a mock result, onboarding) may delight.
- **Page transitions** are React `<ViewTransition>` (the `(app)` layout names
  the region `page`; see `styles/shell.css`). Shared-element morphs (a subject
  card growing into the practice header) use a named `<ViewTransition
  name="…" share="morph" default="none">` on both ends — see
  `node_modules/next/dist/docs/01-app/02-guides/view-transitions.md`.
- **Reduced motion**: the CSS tokens collapse to ~0 and `globals.css` kills
  keyframes; Motion components respect it via
  `MotionConfig reducedMotion="user"`. Every animation must still leave the
  final state correct. Tested, not intended.
- **Exam mode is calm.** No decorative motion, selection feedback ≤ 120 ms and
  purely visual, **never** an animation between a key press and the answer
  being saved. The exam route does not load Motion at all.

### Loading Motion (the budget)

React + the App Router runtime already cost **127 KB** gzipped of each route's
150 KB. So:

- Motion is **not** mounted globally. A client island that uses it imports
  `m` from `motion/react-m` and wraps *itself* in `<MotionProvider>`
  (`components/motion-provider.tsx`, which lazy-loads the features chunk).
  Never import `motion` (the full component) — `strict` mode throws.
- Heavy interactive parts (a practice session, the onboarding flow, the
  landing deck) are code-split with `next/dynamic` or `React.lazy` behind a
  server-rendered first paint, so first-load JS stays inside budget.
- `python tools/web_budget.py` after `npm run build` is the judge. Do not
  change budgets; if one cannot be met, report the numbers.

## Layout

- **Routes.** `app/(site)` public pages (landing `/`, `/pricing`, `/privacy`,
  `/parents`, `/login`, `/signup`) — server-rendered, readable with JS off.
  `app/(app)` the product with the tab bar (`/dashboard`, `/practice`,
  `/reading`, `/exam`, `/tutor`, `/notebook`, `/settings`). `app/(focus)`
  full-screen, no tab bar (`/onboarding`, `/exam/[sessionId]`, practice
  sessions if the feature wants them full-screen).
- **Phone first at 360 px**, then 1024+ gets more room, never different
  features. No horizontal scroll, ever. Tap targets ≥ 44 px. `min-h-[100dvh]`
  never `h-screen`.
- Structure from a hairline and a change of ground, not a grid of identical
  cards. A card is used when elevation means something (the answer artifact,
  a question, a selectable plan).
- **States**: every data view has loading (skeleton in the final shape, not a
  spinner), empty (says how to fill it), error (says what happened and what
  still works) and offline variants.

## Copy

Plain, specific, written for a sixteen-year-old under pressure; Nigerian
English where it reads naturally. Never a dead end: a refusal says what it
cannot do and what it can. No claim about how many past questions Sabi has
(the legal position is open). Numbers on the page come from the API or from
`web/content/*.json`, which `tests/test_landing_facts.py` checks.

## Accessibility

WCAG 2.2 AA in both themes, checked by `python tools/contrast_web.py` from
the real tokens; any hex literal outside `tokens.css` / `lib/theme-colors.ts`
fails it. Visible focus everywhere (`--focus`, saffron on indigo). Screen-
reader labels on icon buttons. Form labels above inputs, errors below, never
placeholder-as-label.

## Where things live

| Thing | File | Owner |
|---|---|---|
| Tokens | `web/styles/tokens.css` | lead (frozen contract) |
| Shared components + motion classes | `web/styles/adire.css` | lead |
| App shell, tab bar, page transition | `web/styles/shell.css`, `web/components/tab-bar.tsx`, `web/app/(app)/layout.tsx` | lead |
| Motion presets | `web/lib/motion.ts`, `web/components/motion-provider.tsx` | lead |
| Feature screens | `web/features/<feature>/**` + thin `page.tsx` files in `web/app/**` | the feature |
| Feature styles | `web/features/<feature>/<feature>.css`, imported by that feature | the feature |
