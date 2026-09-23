# Sabi — Stack currency and commercial research

Research only. Nothing was installed; no package manager was run. All version
numbers below were read live from the npm registry (`registry.npmjs.org/<pkg>/latest`)
on the retrieval date, not from memory.

Retrieval date for everything in this document: **2026-09-23**.

Confidence key:
- **confirmed** — read from the vendor's own site, docs, or registry metadata.
- **probable** — consistent across two or more independent secondary sources, primary source unreachable.
- **unconfirmed** — single secondary source, or figures conflict.

---

## Contradicts the brief

Seven things the brief assumes are wrong, stale, or materially incomplete. Ordered
by how much damage they would do if built on as stated.

### 1. View Transitions need no flag and no workaround in Next.js 16

The brief treats View Transitions as needing a workaround. It does not. As of
Next.js 16.3.6 the component is imported from `react` directly — no `unstable_`
prefix, no `experimental.viewTransition` flag in `next.config`.

- Claim: View transitions work in the Next.js App Router with no configuration. The import is `import { ViewTransition } from 'react'`. The App Router ships React canary internally, so `react@canary` need not be installed.
  Source: https://nextjs.org/docs/app/guides/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `<Link transitionTypes={['nav-forward']}>` and `useRouter().push(url, { transitionTypes })` are documented Next.js APIs for tagging directional navigations.
  Source: https://nextjs.org/docs/app/guides/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

Nearly every blog post still says `experimental: { viewTransition: true }` and
`unstable_ViewTransition`. That advice is a year stale. Follow the Next.js doc,
not the blogs. Caveat below in §Part 1 about the CSS pointer-events trap.

### 2. Tailwind v4's browser floor conflicts with "cheap Android phones"

Tailwind v4 is stable — the brief is right about that. But v4 dropped support for
older browsers, and that is a direct collision with the stated user base.

- Claim: Tailwind CSS v4 requires Safari 16.4+, Chrome 111+, and Firefox 128+. Projects needing older browsers must stay on v3.4.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

On cheap Nigerian Android hardware the browser is usually Chrome (auto-updating,
so likely fine) but a meaningful tail runs Opera Mini, UC Browser, or a vendor
WebView pinned to an old Chromium. Tailwind v4 output will not degrade
gracefully on those — it emits `oklch()` colors, `@property`, and cascade layers.
This needs a real device-and-browser measurement before it is locked in. It is
the single biggest technical risk in the proposed stack.

### 3. "Zod v3 vs v4 matters" is no longer true for the RHF/shadcn path

- Claim: `@hookform/resolvers@5.9.1` declares `zod` as an optional peer with the range `^3.25.0 || ^4.0.0`. Both major versions are supported by the same resolver release.
  Source: https://registry.npmjs.org/@hookform/resolvers/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: current stable Zod is `4.6.5`.
  Source: https://registry.npmjs.org/zod/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

The real breaking change is not Zod's major version, it is `@hookform/resolvers`
v3 → v5: the import moved from `@hookform/resolvers/zod` default-style usage to
named `zodResolver`, and v4/v5 changed the resolver's generic signature. Start on
Zod 4.6.x and resolvers 5.9.x and this is a non-issue. Do not spend a decision on it.

### 4. TypeScript is on 7.x, not 5.x

- Claim: current stable TypeScript is `7.0.2`.
  Source: https://registry.npmjs.org/typescript/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: TypeScript 7.0 is real and in production use by library authors — Serwist's 9.5.12 maintenance release (2026-07-22) is described as "monthly maintenance & bump TypeScript to 7.0".
  Source: https://api.github.com/repos/serwist/serwist/releases/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

TS 7 is the native (Go) compiler port. It is dramatically faster but it is a new
implementation. Expect type-checking edge cases and ecosystem plugins (ESLint
type-aware rules, older `ts-node`-style tooling) to be the friction point, not the
compiler itself. Note that several libraries still declare `typescript: >=5.0.0`
as an optional peer, which will resolve fine against 7.x but means they have not
explicitly certified it.

### 5. Serwist is alive, but the Next.js 16 integration package changed

The brief's concern is fair in spirit but the answer is not the one it expects.
Serwist is maintained and does support Next.js 16 — but the webpack-based
`@serwist/next` is no longer the right entry point, because Next.js 16 defaults
to Turbopack.

- Claim: `@serwist/next` is at `9.5.12`, peer `next: >=14.0.0`, repo not archived, last push 2026-07-22, 9 open issues, ~1,485 stars.
  Source: https://registry.npmjs.org/@serwist/next/latest and https://api.github.com/repos/serwist/serwist
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: a separate package `@serwist/turbopack@9.5.12` exists, described as "A module that integrates Serwist into your Next.js / Turbopack application", peer `next: >=14.0.0`.
  Source: https://registry.npmjs.org/@serwist/turbopack/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: Serwist issue #301 "Support next.js 16" is closed/completed (opened 2025-11-05). Subsequent Next 16 issues were filed and closed: #335 and #336 (esbuild-wasm resolution failures on Next 16.1.6 with Turbopack, needing `serverExternalPackages`), #357 (`SerwistProvider` missing `"use client"`, Next 16.2.4).
  Source: https://api.github.com/search/issues?q=repo:serwist/serwist+%22next+16%22
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: issue **#360 "createSerwistRoute crashes at runtime on Vercel" is OPEN**, filed 2026-07-21 against Next.js 16.2.10, describing runtime failure on edge cache miss.
  Source: https://api.github.com/search/issues?q=repo:serwist/serwist+%22next+16%22
  Retrieved: 2026-09-23
  Confidence: confirmed

So: Serwist is the right choice, use `@serwist/turbopack`, and test the service
worker route on the real deploy target early because there is a live unresolved
production bug in that area.

### 6. "DLT registration" is India, not Nigeria

The brief asks about "DLT/sender-ID registration requirements in Nigeria". DLT
(Distributed Ledger Technology registration) is the Indian TRAI regime. Nigeria
has no DLT equivalent. It has a different, and in practice slower, requirement.

- Claim: Nigerian sender ID registration is done per-operator — a formal application on company letterhead to each of MTN, Airtel, Glo and 9mobile, with CAC certificate, sample message content and director signature. Typically 2–3 weeks for domestic IDs.
  Source: https://www.bulksmsnigeria.com/resources/sender-id-guide
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: to reach numbers on the NCC Do-Not-Disturb list (shortcode 2442; >30 million Nigerian numbers registered as of 2024), the sender ID must be registered on the **transactional bind**. Promotional SMS is restricted to 08:00–20:00 WAT; transactional/DND-route traffic is not time-restricted.
  Source: https://www.bulksmsnigeria.com/resources/sms-compliance-nigeria and https://www.sent.dm/resources/nigeria-sms-guide
  Retrieved: 2026-09-23
  Confidence: probable

This matters more than the brief allows: **CAC registration is a prerequisite for
sender-ID registration**, and sender-ID registration is a prerequisite for OTPs
reaching a third of Nigerian phones. That couples the "Paystack Starter Business
before CAC" plan to the guardian-consent OTP feature. See Part 2 and Part 3.

### 7. ALOC's legacy sunset is real and dated, and the successor costs money

- Claim: the legacy API at questions.aloc.com.ng carries the notice "This legacy version is reaching end-of-life in 12 months (from August 1st, 2026)", directing users to ALOC Station at aloc.com.ng for the new API infrastructure. That puts EOL at approximately **1 August 2027**.
  Source: https://questions.aloc.com.ng/
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: legacy ALOC pricing is Access ₦0 (7,000 calls), Basic ₦2,000 (20,000 calls), Huge ₦5,000 (unlimited / 120,000 calls).
  Source: https://questions.aloc.com.ng/
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: ALOC Station pricing is Free ₦0 (1,000 credits, L1 + 100 trial L2–L4), Developer ₦5,000/month (50,000 credits, L1–L3), Growth ₦20,000/month (500,000 credits, L1–L4), Enterprise custom.
  Source: https://aloc.com.ng/
  Retrieved: 2026-09-23
  Confidence: confirmed

The shape changed: legacy was a near-one-off payment, Station is a **monthly**
subscription with credit metering and tiered content levels. If the brief's
business model assumed ALOC as a cheap one-time data source, that assumption
expires in August 2027 and the replacement is ₦5,000–₦20,000/month.

---

## Part 1 — Library versions and API currency

### Core framework

- Claim: Next.js current stable is `16.3.6` (published ~2026-09-22).
  Source: https://registry.npmjs.org/next/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: React current stable is `19.3.0`.
  Source: https://registry.npmjs.org/react/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: TypeScript current stable is `7.0.2`.
  Source: https://registry.npmjs.org/typescript/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

Breaking-change note: Next.js 16 defaults to Turbopack for both dev and build.
Any webpack-specific config (custom loaders, `webpack()` in `next.config`) is the
first thing that will break, and it is what caused the Serwist issues above.

### Tailwind CSS

- Claim: Tailwind CSS current stable is `4.3.3`. v4 is stable, so the brief is correct to assume v4.
  Source: https://registry.npmjs.org/tailwindcss/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

The v3 → v4 differences that break a naive implementation, all from the official
upgrade guide:

- Claim: configuration moved from JavaScript `tailwind.config.js` to CSS-first `@theme { --color-*: ...; --breakpoint-*: ...; --font-*: ...; }`.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: the three directives `@tailwind base; @tailwind components; @tailwind utilities;` are replaced by the single `@import "tailwindcss";`.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: the PostCSS plugin moved from the `tailwindcss` package to `@tailwindcss/postcss`. The CLI moved from `npx tailwindcss` to `npx @tailwindcss/cli`. Vite projects should use the dedicated `@tailwindcss/vite` plugin instead of PostCSS.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: custom utilities move from `@layer utilities` to the `@utility` directive.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: removed utilities — `bg-opacity-*`, `text-opacity-*`, `border-opacity-*` (use `bg-black/50` slash syntax), `flex-shrink-*` → `shrink-*`, `flex-grow-*` → `grow-*`, `overflow-ellipsis` → `text-ellipsis`, `decoration-slice`/`decoration-clone` → `box-decoration-*`.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: **silently renamed** scale utilities — `shadow-sm` → `shadow-xs`, bare `shadow` → `shadow-sm`, `drop-shadow-sm` → `drop-shadow-xs`, `blur-sm` → `blur-xs`, `rounded-sm` → `rounded-xs`, `outline-none` → `outline-hidden`, bare `ring` → `ring-3`.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

That rename list is the dangerous one. `shadow-sm` and `rounded-sm` still compile
in v4 — they just mean something one step larger than they used to. Nothing
errors; the design just quietly drifts. Any v3 snippet pasted from an LLM or a
blog will be subtly wrong.

- Claim: `npx @tailwindcss/upgrade` automates most of the migration and requires Node.js 20+.
  Source: https://tailwindcss.com/docs/upgrade-guide
  Retrieved: 2026-09-23
  Confidence: confirmed

### shadcn/ui and Radix

- Claim: the `shadcn` CLI package is at `4.21.0`.
  Source: https://registry.npmjs.org/shadcn/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: the unified `radix-ui` package is at `1.6.7`, peer `react: ^16.8 || ^17.0 || ^18.0 || ^19.0`.
  Source: https://registry.npmjs.org/radix-ui/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: shadcn CLI v4 (March 2026) supports Next.js, Vite, Laravel, React Router, Astro and TanStack Start templates, and adds a `--base` flag to choose **Radix or Base UI** as the primitive layer. New flags: `--dry-run`, `--diff`, `--view`, `--preset`, `--template`. Registries can ship a whole design system via `registry:base`.
  Source: https://ui.shadcn.com/docs/changelog/2026-03-cli-v4
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: the shadcn Next.js install page gives `pnpm create next-app@latest` with no pinned version, and does not name a Next.js version, React version or Tailwind version.
  Source: https://ui.shadcn.com/docs/installation/next
  Retrieved: 2026-09-23
  Confidence: confirmed

Answer to "does shadcn/ui support the current Next.js and Tailwind versions":
**yes for Tailwind v4 and React 19, which are explicitly supported; for Next.js
16 it is not explicitly stated anywhere I could find.** The docs use `@latest`,
which resolves to 16.3.6 today, which is a strong implicit signal, but it is an
inference rather than a stated guarantee. Listed under "Could not confirm".

- Claim: shadcn/ui form primitives (`Form`/`FormField`/`FormItem`/`FormControl`/`FormMessage`) are built on React Hook Form and Zod, and shadcn's verified dependency set as of June 2026 includes Zod v4.
  Source: https://tomodahinata.com/en/blog/react-hook-form-shadcn-ui-zod-form-components-guide
  Retrieved: 2026-09-23
  Confidence: probable

### Data, state, forms

- Claim: `@tanstack/react-query` is at `5.103.2`, peer `react: ^18 || ^19`.
  Source: https://registry.npmjs.org/@tanstack/react-query/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `zustand` is at `5.0.15`, with all peers optional (`react >=18`, `immer >=9.0.6`, `@types/react >=18`, `use-sync-external-store >=1.2.0`).
  Source: https://registry.npmjs.org/zustand/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `react-hook-form` is at `7.88.0`, peer `react: ^16.8.0 || ^17 || ^18 || ^19`.
  Source: https://registry.npmjs.org/react-hook-form/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `@hookform/resolvers` is at `5.9.1`.
  Source: https://registry.npmjs.org/@hookform/resolvers/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `zod` is at `4.6.5`.
  Source: https://registry.npmjs.org/zod/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

Zustand v5 breaking change to watch: v5 removed the default export and the
deprecated `create` without a curried call in TypeScript — use
`create<State>()(...)` with the extra parentheses. Not verified against the
changelog in this pass; treat as a known-gotcha to check at install time.

- Claim: `openapi-typescript` is at `7.13.0`, "Convert OpenAPI 3.0 & 3.1 schemas to TypeScript".
  Source: https://registry.npmjs.org/openapi-typescript/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

Note that `openapi-typescript` v7 emits types only. If runtime fetching with those
types is wanted, that is the separate `openapi-fetch` package.

### Service worker / PWA

Covered in §5 of "Contradicts the brief". Summary: Serwist is maintained
(`@serwist/next@9.5.12`, `@serwist/turbopack@9.5.12`, repo active as of
2026-07-22, not archived), it supports Next.js 16, and `@serwist/turbopack` is
the package to use because Next 16 defaults to Turbopack. There is no need to
look for an alternative; `next-pwa` remains the abandoned predecessor Serwist
replaced.

### Animation

- Claim: the package is named `motion` (not `framer-motion`) and is at `13.4.1`, described as "An animation library for JavaScript and React", optional peers `react`/`react-dom: ^18.0.0 || ^19.0.0`.
  Source: https://registry.npmjs.org/motion/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `LazyMotion` and the `m` component still exist and are current, not deprecated. Imports are `import { LazyMotion, domAnimation } from "motion/react"` and `import * as m from "motion/react-m"`. This reduces the initial render cost to ~4.6kb with the remaining features sync- or async-loaded.
  Source: https://motion.dev/docs/react-lazy-motion
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: Motion 13 breaking change — `@emotion/is-prop-valid` was removed as an optional dependency in favour of explicit injection via `<MotionConfig isValidProp={isPropValid}>`. Motion 13 also made `LazyMotion` share React context between the main and `/m` bundles so `<m.div>` picks up features loaded by `<LazyMotion>`.
  Source: https://motion.dev/docs/react-upgrade-guide
  Retrieved: 2026-09-23
  Confidence: probable

The `LazyMotion` + `m` path is worth taking here specifically because of the
cheap-Android constraint — it is the difference between ~4.6kb and ~34kb on first
paint.

- Claim: GSAP is at `3.15.0`. Its npm `license` field reads: "Standard 'no charge' license: https://gsap.com/standard-license."
  Source: https://registry.npmjs.org/gsap/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: GSAP is free for commercial use, and this explicitly includes the formerly members-only Club plugins such as SplitText and MorphSVG. The standard license grants a "non-exclusive, worldwide license to use, reproduce, display, and implement GSAP Products solely for Permitted Uses."
  Source: https://gsap.com/standard-license/
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: Webflow acquired GreenSock in late 2024 and made GSAP 100% free, including all Club plugins, from April 2025.
  Source: https://webflow.com/updates/gsap-becomes-free
  Retrieved: 2026-09-23
  Confidence: confirmed

The brief is **correct** on GSAP, with one caveat it does not mention: the
license carves out "Prohibited Uses" — you may not use GSAP to build tools that
let users create animations through a visual interface competing with Webflow.
An exam-prep platform is nowhere near that line, so this is a non-issue for Sabi,
but it should be recorded because it means the licence is not unconditional.

- Claim: `lenis` is at `1.3.26`.
  Source: https://registry.npmjs.org/lenis/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `@formkit/auto-animate` is at `0.10.0`.
  Source: https://registry.npmjs.org/@formkit/auto-animate/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `lucide-react` is at `1.47.0`, peer `react: ^16.5.1 || ^17.0.0 || ^18.0.0 || ^19.0.0`.
  Source: https://registry.npmjs.org/lucide-react/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `@rive-app/react-canvas` is at `4.34.3`, peer `react: ^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0`.
  Source: https://registry.npmjs.org/@rive-app/react-canvas/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `@lottiefiles/dotlottie-react` is at `0.19.16`, peer `react: ^17 || ^18 || ^19`.
  Source: https://registry.npmjs.org/@lottiefiles/dotlottie-react/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

Note that dotlottie-react is still pre-1.0 (`0.19.x`) — minor bumps may break.
Also note both Rive and dotLottie ship a WASM runtime; on a low-end Android phone
that is a meaningful download and parse cost on top of Lenis and GSAP. Pick one,
not both.

Lenis specifically: smooth-scroll hijacking is the most commonly reported
accessibility and low-end-performance complaint in this category. Given the
target hardware, this is the one library in the list I would challenge before
adopting.

### Testing and quality

- Claim: `@playwright/test` is at `1.63.0`.
  Source: https://registry.npmjs.org/@playwright/test/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `vitest` is at `5.0.1`.
  Source: https://registry.npmjs.org/vitest/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `axe-core` is at `4.13.0`.
  Source: https://registry.npmjs.org/axe-core/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: `@lhci/cli` (Lighthouse CI) is at `0.15.1`.
  Source: https://registry.npmjs.org/@lhci/cli/latest
  Retrieved: 2026-09-23
  Confidence: confirmed

Vitest 5 is a new major — the config surface (`environment`, `deps.inline`,
workspace/projects) changed from v3/v4 era guides. Check the migration guide
rather than copying an existing config.

### View Transitions API — browser support

This is the part that matters for cheap Android phones, so the numbers are given
precisely.

- Claim: same-document View Transitions are **Baseline: newly available** with a baseline low date of **2025-10-14**. Per-browser first support: Chrome 111 (2023-03-07), **Chrome Android 111 (2023-03-07)**, Edge 111 (2023-03-13), Safari 18 (2024-09-16), Safari iOS 18 (2024-09-16), Firefox 144 (2025-10-14).
  Source: https://api.webstatus.dev/v1/features/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: global usage support for View Transitions is **91.75%**. Samsung Internet supports it from version 23.
  Source: https://caniuse.com/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: **cross-document** (MPA) View Transitions are **Baseline: limited** — Chrome 126 and Chrome Android 126 (2024-06-11), Safari and Safari iOS 18.2 (2024-12-11), **no available Firefox release**.
  Source: https://api.webstatus.dev/v1/features/cross-document-view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

Android Chrome specifically: **supported since Chrome 111, March 2023**. Chrome on
Android auto-updates aggressively even on low-end devices, so for the Sabi
audience this is effectively universal among Chrome users. Samsung Internet 23+
covers most Samsung budget handsets. The gap is Opera Mini (no support, and it is
non-trivially used in Nigeria on data-saver/extreme mode) and old vendor WebViews.

- Claim: React's View Transitions integration uses newer features of the API (transition types and `view-transition-class`) available in **Chromium 125+** and recent Safari and Firefox. Without browser support the application works normally; the transitions simply do not animate.
  Source: https://nextjs.org/docs/app/guides/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

So the effective floor for the React/Next.js flavour is Chromium 125, not 111.
Graceful degradation is automatic — this is safe to ship as progressive
enhancement with no feature detection code.

Two traps worth writing down now, both from the Next.js guide:

- Claim: while a transition runs, the `::view-transition` overlay captures pointer events and clicks are lost. The fix is `::view-transition { pointer-events: none; }`. Hit-testing still skips named participants for the transition's duration.
  Source: https://nextjs.org/docs/app/guides/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: browser-initiated back navigation (back button, swipe gesture) does not carry a transition type, so directional slides will not play for it. `<ViewTransition>` wrappers must go in each `page.tsx`, not in a layout, because layouts persist across navigations and so enter/exit never fire there.
  Source: https://nextjs.org/docs/app/guides/view-transitions
  Retrieved: 2026-09-23
  Confidence: confirmed

The dropped-click behaviour is the one that would actually hurt Sabi — a student
tapping quickly through practice questions on a slow phone would lose taps during
the animation. Ship the `pointer-events: none` rule from day one and keep
transition durations short.

---

## Part 2 — Payments

### Paystack webhook verification

Paystack's own developer docs (paystack.com/docs/*) return HTTP 403 to automated
fetchers, including with a browser user-agent, so the primary source could not be
read directly. The following is corroborated across multiple independent
secondary sources that agree exactly, and matches the brief.

- Claim: **the brief is correct.** Paystack signs each webhook with **HMAC-SHA512 over the raw request body, hex-encoded**, delivered in the **`x-paystack-signature`** header. The key is your Paystack **secret key** (`sk_test_…` / `sk_live_…`) — the same key used for API calls, not a separate webhook secret.
  Source: https://hookdeck.com/webhooks/skills/paystack-webhooks and https://www.mctaba.com/learn/paystack/paystack-webhooks-complete-engineering-guide
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: you must verify against the **raw body bytes**, not a re-serialized JSON object. Do not `JSON.parse` before verifying. Compare in constant time.
  Source: https://www.mctaba.com/learn/paystack/paystack-webhooks-complete-engineering-guide
  Retrieved: 2026-09-23
  Confidence: probable

In Next.js this means the webhook route must read `await req.text()` and hash
that string, then parse. Any middleware or body parser that normalises the body
will silently break signature verification.

- Claim: Paystack's webhook source IPs are **52.31.139.75, 52.49.173.169, 52.214.14.220**, applicable to both test and live environments; requests from other IPs should be considered counterfeit.
  Source: https://support.paystack.com/en/articles/2130946 (title "IP whitelisting"), corroborated at https://www.mctaba.com/learn/paystack/paystack-webhook-ip-allowlisting-how-and-when
  Retrieved: 2026-09-23
  Confidence: probable

IP allowlisting is an optional extra layer, not a replacement for signature
verification. On Vercel or similar serverless hosting you generally cannot
allowlist at the network edge anyway, so rely on the HMAC.

- Claim: retry schedule — in **live mode**, events are retried every 3 minutes for the first 4 attempts, then hourly for the next 72 hours. In **test mode**, hourly for 10 hours. Request timeout is **30 seconds**.
  Source: https://hookdeck.com/webhooks/platforms/guide-to-paystack-webhooks-features-and-best-practices
  Retrieved: 2026-09-23
  Confidence: probable

Note one source (mctaba) states the exact retry schedule is "not publicly
documented with fixed numbers", which conflicts with the Hookdeck figures. Treat
the 3-min×4-then-hourly-for-72h figure as probable, and design so that the exact
schedule does not matter: idempotent handler, 200 fast, reconcile separately.

- Claim: idempotency guidance — use the event type plus `data.id` / transaction `reference` as a deduplication key, persisted, so the 72-hour retry window cannot double-grant entitlement. Return 200 quickly and do the work asynchronously.
  Source: https://www.mctaba.com/learn/paystack/paystack-webhooks-complete-engineering-guide and https://hookdeck.com/webhooks/skills/paystack-webhooks
  Retrieved: 2026-09-23
  Confidence: probable

### Paystack transaction verification

- Claim: the endpoint is **`GET https://api.paystack.co/transaction/verify/{reference}`**, authenticated with `Authorization: Bearer YOUR_SECRET_KEY`. It is a server-only call.
  Source: https://paystack.com/docs/payments/verify-payments/ (via search result extract) and https://www.postman.com/paystack-developers/paystack-api/request/9joxt4x/verify-transaction
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: the top-level `response.status` is the status of the **API call**, not of the transaction. The transaction status is at **`response.data.status`**. Confusing the two is the standard integration bug.
  Source: https://paystack.com/docs/payments/verify-payments/ (via search result extract)
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: the verify endpoint is idempotent — calling it repeatedly for the same reference returns the same result, so it is safe to retry on network failure.
  Source: https://www.mctaba.com/learn/paystack/verify-transaction-the-paystack-call-you-must-never-skip
  Retrieved: 2026-09-23
  Confidence: probable

The correct entitlement flow, which the brief should adopt if it does not already:
verify the HMAC → dedupe on reference → call `GET /transaction/verify/{reference}`
→ assert `data.status === "success"` **and** `data.amount` and `data.currency`
match what you expected for that plan → only then grant. Never grant on the
webhook payload alone, and never grant on the browser callback alone.

### Paystack Starter Business collection limit

This is the real number the brief asked for.

- Claim: Nigerian Paystack **Starter Business** accounts have a **lifetime collections limit of ₦8,000,000** (stated alongside a USD 5,000 equivalent for dollar collections). On reaching it, "payments for your business will be temporarily disabled." Removing the cap requires upgrading to a Registered Business from the Compliance page on the dashboard, which requires CAC registration (BN or RC).
  Source: https://support.paystack.com/en/articles/2128898
  Retrieved: 2026-09-23
  Confidence: confirmed

This is Paystack's own support site, read directly. **₦8,000,000 lifetime, not
annual, not per-transaction.** Per-transaction amounts are unrestricted as long
as the lifetime total stays under.

Practical consequence for Sabi: at, say, a ₦2,000 plan, ₦8,000,000 is roughly
4,000 paid subscriptions — reachable. The brief's instinct to build an admin
alert is right. Set the alert at ₦6,000,000 (75%), not at 95%, because CAC
registration plus the Paystack compliance upgrade plus per-operator SMS sender-ID
registration are all multi-week processes that should be started well before the
cap bites. Payments being "temporarily disabled" mid-term with no fallback would
be the worst outcome.

### Flutterwave as a fallback

One thing makes Flutterwave materially **harder** to secure, and it is worth
recording rather than discovering later.

- Claim: Flutterwave does not use a per-request HMAC. It sends a **static** `verif-hash` header containing a hash of a secret you set in the dashboard. The value does not change between requests and **does not include the request body**, so it provides no body integrity at the application layer — it is functionally a static bearer token, with body integrity resting entirely on TLS.
  Source: https://developer.flutterwave.com/docs/webhooks
  Retrieved: 2026-09-23
  Confidence: probable

Consequences if Flutterwave is used as a fallback: the shared secret must be
rotated periodically, IP allowlisting becomes more valuable than it is with
Paystack, and — most importantly — the **re-verify-before-granting step stops
being best practice and becomes mandatory**, because a leaked `verif-hash` lets
anyone forge an arbitrary payment-success body. Since the architecture should
re-verify for Paystack anyway, adding Flutterwave is cheap: the same "never trust
the webhook body" discipline covers both. Make the abstraction
provider-independent from the start.

Flutterwave is otherwise broadly comparable for Nigerian collections and has
wider pan-African coverage, which would matter only if Sabi expands beyond
Nigeria.

---

## Part 3 — Email and SMS to Nigeria

### Recommendation

**SMS — first choice: Termii. Runner-up: Sendchamp.**
**Email — first choice: Postmark. Runner-up: Resend.**

#### Why Termii for SMS

The deciding factor the brief names is deliverability to Nigerian networks, and
the specific technical thing that determines it is **DND-route access**. Over 30
million Nigerian numbers are on the NCC Do-Not-Disturb list; a guardian-consent
OTP that silently fails for a third of guardians is a broken feature, not a
degraded one. Termii is Nigerian-founded, sends across both generic and DND
routes, and its documented operational process is exactly the one needed —
sender ID whitelisting for the transactional/DND bind, requested through support.

- Claim: Termii is a Nigerian-founded communications API delivering SMS, voice OTP, email and WhatsApp, focused on Nigerian and African carriers, reaching all four networks (MTN, Airtel, Glo, 9mobile) with NGN-denominated pricing.
  Source: https://developers.termii.com/messaging-api
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Termii sends across generic and DND routes. To send on the DND (transactional) route, the sender ID must be whitelisted for DND messaging, requested via support, and the DND route must be activated on the account.
  Source: https://developers.termii.com/messaging-api
  Retrieved: 2026-09-23
  Confidence: probable

Sendchamp is the runner-up on the same logic — Nigerian-founded, NGN pricing,
carrier-optimised, single API across SMS/WhatsApp/voice/email — and would be a
genuinely close call. It ranks second only because Termii's DND-route handling is
the more explicitly documented of the two, and because Sendchamp's own pricing
page currently renders incomplete data (see below), which is a small signal about
operational polish for something on the critical path of account creation.

- Claim: Sendchamp is a Nigerian-founded multi-channel messaging platform with a unified API for SMS, WhatsApp Business, voice OTP and email, with NGN pricing and Nigerian-carrier-optimised delivery.
  Source: https://sendchamp.com/best-termii-alternative
  Retrieved: 2026-09-23
  Confidence: probable

A material caveat on Termii that changes the commercial picture:

- Claim: Termii's pricing page no longer publishes a per-message rate card. It states "Rates vary by destination and channel. Talk to sales for your current rate card", and bills SMS, WhatsApp and Email per transaction on top of an "Engage, Resolve, or Signals" platform subscription.
  Source: https://termii.com/pricing
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: Termii paid plans are reported to start at $25 per agent per month.
  Source: https://www.buildstudio.com.ng/apis/termii-api
  Retrieved: 2026-09-23
  Confidence: unconfirmed

Termii has evidently moved upmarket toward a platform/seat model. For Sabi that
means a sales conversation before a firm cost is known. If that seat fee is real
and applies, Sendchamp may win on cost — get both rate cards before committing.

#### Typical cost per SMS

- Claim: OTP SMS on domestic/local Nigerian routes runs roughly **₦1.80–₦6.00 per message** (about $0.001–$0.004).
  Source: https://www.messagecentral.com/blog/otp-sms-pricing-nigeria
  Retrieved: 2026-09-23
  Confidence: probable

DND-route transactional messages sit at the upper end of that band. Budget ~₦4–6
per guardian-consent OTP and assume one retry, so ~₦8–12 per completed consent.

#### Registration requirements (the real answer to the "DLT" question)

There is no DLT in Nigeria. What is required:

- Per-operator sender ID registration with MTN, Airtel, Glo and 9mobile —
  application on company letterhead, **CAC certificate**, sample message content,
  director's signature. ~2–3 weeks.
- Registration on the **transactional bind** specifically, to reach DND numbers.
- Promotional traffic is restricted to 08:00–20:00 WAT; transactional is not.

Sources and confidence as given in §6 of "Contradicts the brief".

The CAC dependency is the scheduling risk. Sender-ID registration needs CAC, and
so does lifting the Paystack ₦8m cap. Both should be started at the same time,
early, not when each becomes urgent.

#### Why Postmark for email

Guardian-consent codes are the definition of transactional mail: low volume, high
stakes, must land in the inbox within seconds. Postmark's entire product position
is that one job, with hard separation between transactional and bulk streams so
marketing mail can never poison the reputation of the stream carrying consent
codes. It also publishes real delivery statistics rather than asserting them.

- Claim: Postmark has sent transactional mail since 2010 with strict separation between transactional and bulk sending, publishes real-time delivery stats (98%+ inbox placement), and a 10s median delivery speed. An independent 2026 EmailTooltester test measured a 93.8% average inbox placement, with three of four rounds at 95–97%.
  Source: https://postmarkapp.com/compare/resend-alternative
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Postmark pricing is free 100/month, $15/month for 10K, $55/month for 50K. Resend is free 3K/month and $20/month for 50K.
  Source: https://nuntly.com/versus/resend-vs-postmark
  Retrieved: 2026-09-23
  Confidence: probable

Resend is the runner-up: much cheaper at volume, excellent developer experience,
React Email templating. It loses on the deciding criterion because it launched in
2023 and publishes far less deliverability evidence, and because the brief
explicitly says deliverability decides, not price. At Sabi's likely consent-email
volumes the absolute difference is $15 vs $20 a month — not worth optimising.

Note that the two big Nigerian inbox destinations are Gmail and Yahoo, both of
which now enforce bulk-sender authentication. Whichever provider is chosen, SPF,
DKIM and a DMARC record on the sending domain are mandatory, not optional.

A consolidation option worth considering: Termii and Sendchamp both offer email
as well as SMS, so one vendor could cover both. I would not do it. Email
deliverability is a specialist discipline and these providers' strength is
carrier SMS, not inbox placement at Gmail. Keep SMS local and email specialist.

---

## Part 4 — Competitor prices

### ALOC

Covered fully in §7 of "Contradicts the brief". Legacy: ₦0 / ₦2,000 / ₦5,000
tiers, EOL ~1 August 2027. Successor "ALOC Station": ₦0 / ₦5,000 / ₦20,000 per
month with credit metering and L1–L4 content levels. Both read directly from the
vendor's sites; **confirmed**.

### Passnownow

- Claim: Passnownow plans, read from its own subscription page — Daily ₦300 (24 hrs), Weekly ₦600 (168 hrs), Monthly ₦1,100 (720 hrs), Quarterly ₦2,600 (2,160 hrs), Half-year ₦5,100 (4,320 hrs), Yearly ₦10,100 (8,760 hrs). Every tier buys identical access: all class notes and past questions across JSSCE, SSCE and UTME/JAMB. Card payment activates instantly; bank transfer takes up to four hours.
  Source: https://passnownow.com/subscription/
  Retrieved: 2026-09-23
  Confidence: confirmed

What the price buys: notes plus past questions, text-based, no video. The daily
₦300 tier is the interesting competitive datapoint — it is priced for a student
cramming the night before, which is a real Nigerian usage pattern and a price
point Sabi may need an answer to.

### Class54

- Claim: Class54 plans, read from its own pricing page — Basic ₦2,000 (1 month), Premium ₦3,000 (3 months), Platinum ₦5,000 (1 year). All tiers unlock the same content: 27+ years of JAMB past questions with detailed explanations, Post-UTME material for 50+ Nigerian institutions, WAEC theory and objective resources, JAMB-curriculum study notes, performance analytics, topic-based practice and a voice assistant. No free tier is offered; registration is required to subscribe.
  Source: https://class54.com/pricing
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: Class54 advertises 112,000+ past questions and offline practice for JAMB UTME CBT, Post-UTME and WAEC.
  Source: https://class54.com/
  Retrieved: 2026-09-23
  Confidence: probable

Note the shape: ₦5,000 buys a **year**, versus Passnownow's ₦10,100. Class54 is
roughly half Passnownow's annual price for a comparable question bank, and its
tier ladder is steeply discounted toward the long plan. That is the price to beat.

### myschool.ng

- Claim: myschool.ng's CBT apps and software use a **one-time activation** model — "No renewal, weekly or monthly payments — once activated, it remains activated for the lifetime of that device", "No hidden charges — all features unlocked at once". Discounted pricing exists for agents, resellers and bulk purchases.
  Source: https://myschool.ng/latest-waec-past-questions-app-free-download
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: the app advertises 60,000+ past questions across JAMB CBT, WAEC, NECO and entrance exams.
  Source: https://play.google.com/store/apps/details?id=com.myschool.cbt
  Retrieved: 2026-09-23
  Confidence: probable

**The activation price could not be found without signing up.** The product pages
describe the model and route to phone/email (+234-913-373-3736, +234-814-666-9200,
info@myschool.ng) or to the app stores rather than stating a figure; the Play
Store and App Store listings could not be read (App Store returned HTTP 429, Play
Store content truncated before the in-app-purchase section). No figure is given
here rather than a guessed one. The structural fact — **one-time, per-device,
lifetime** — is confirmed and is the more strategically important half, because it
is a fundamentally different model from Sabi's presumed subscription.

### uLesson

**Price could not be confirmed. Secondary sources conflict and no primary source
states a figure.**

- Claim: uLesson plans are ₦12,000 (3 months), ₦25,000 (6 months), ₦150,000 (lifetime).
  Source: https://brands.ng/ulesson-review-2026-africas-1-learning-app-for-waec-jamb-better-grades/
  Retrieved: 2026-09-23
  Confidence: unconfirmed

- Claim: uLesson plans are ₦20,000 (3 months), ₦50,000 (6 months), ₦150,000 (lifetime).
  Source: https://techpoint.africa/news/ulesson-halves-educational-subscription-fees-nigeria/
  Retrieved: 2026-09-23
  Confidence: unconfirmed

- Claim: uLesson cut subscription prices by 50% in February 2024 in response to inflation, and at the same time discontinued Live Lessons for grades 1–11 (retaining SS3 only) and removed the Homework Help feature, replacing it with a separate AI app, "Ask by uLesson".
  Source: https://blog.ulesson.com/blog/prices-drop-and-changes-on-learning-plans-on-the-ulesson-app/ (post dated 2024-02-20)
  Retrieved: 2026-09-23
  Confidence: confirmed

The two figure sets differ by a factor of ~2 on both the 3- and 6-month plans,
which is exactly what you would expect if one source quotes pre-cut and the other
post-cut prices. `ulesson.com/pricing` returns HTTP 404; the homepage carries no
pricing; the official blog post announcing the new prices publishes them **only
as an image**, which the fetcher cannot read. Only the ₦150,000 lifetime figure
agrees across sources, and even that is from 2024.

If uLesson's price matters to positioning, someone should open
blog.ulesson.com/blog/prices-drop-and-changes-on-learning-plans-on-the-ulesson-app/
in a browser and read the price-list image, or check the in-app purchase list on
a phone. Do not plan against either figure above.

What is clear regardless: uLesson is an order of magnitude more expensive than
Class54 or Passnownow, because it sells video instruction rather than a question
bank. It is not Sabi's direct price competitor — Class54 is.

---

## Could not confirm

Ordered by how much the gap matters.

1. **uLesson's current prices.** Two secondary sources conflict by ~2×
   (₦12,000/₦25,000 vs ₦20,000/₦50,000 for 3/6 months). `ulesson.com/pricing`
   is a 404; the official announcement publishes the figures only as an image.
   Only ₦150,000 lifetime is consistent, and that is from a Feb 2024 post.
   **Needs a human with a browser or a phone.**

2. **myschool.ng's activation price.** The one-time/per-device/lifetime model is
   confirmed, the figure is not. App Store returned HTTP 429; Play Store content
   truncated before the in-app-purchase section. Recoverable by opening the Play
   Store listing on a phone or calling the published numbers.

3. **Paystack's primary developer docs could not be read at all.** Every
   `paystack.com/docs/*` URL returns HTTP 403 to automated fetchers, including
   via curl with a browser user-agent (Cloudflare). Every Paystack *technical*
   claim in Part 2 — HMAC-SHA512, `x-paystack-signature`, raw-body requirement,
   IP list, retry schedule, verify endpoint path, `response.data.status` — is
   therefore marked **probable**, corroborated across independent secondary
   sources that agree with each other and with the brief. The *commercial* claim
   (₦8,000,000 Starter cap) IS confirmed, because `support.paystack.com` is not
   behind the same block. **Someone should open the docs in a browser and
   confirm the technical details before the payment code is written.**

4. **Paystack's exact retry schedule.** Hookdeck gives 3 minutes × 4 attempts
   then hourly for 72 hours (live) and hourly for 10 hours (test), 30s timeout.
   McTaba states the schedule is "not publicly documented with fixed numbers".
   These conflict. Design the handler to be idempotent and schedule-independent
   so this does not need resolving.

5. **shadcn/ui's explicit support for Next.js 16.** shadcn explicitly supports
   Tailwind v4 and React 19. For Next.js 16 I found no explicit statement
   anywhere — the install docs simply say `pnpm create next-app@latest`, which
   today resolves to 16.3.6. That is a strong implicit signal but it is an
   inference, not a guarantee. The shadcn CLI v4 changelog makes no version
   claims about Next.js, Tailwind, React or Zod.

6. **Termii's and Sendchamp's actual per-message Nigerian rates.** Termii's
   pricing page has removed its rate card in favour of "talk to sales" and a
   platform-subscription model; the reported "$25 per agent per month" entry
   price is from a single secondary source and is **unconfirmed**. Sendchamp's
   pricing page renders "Not Available/sms", "Not Available/email" and "NGN NaN"
   for voice. Neither vendor's real cost to Sabi can be stated without contacting
   sales. The ₦1.80–₦6.00 industry band is a planning proxy only.

7. **Nigerian sender-ID and DND registration specifics** are all **probable**,
   sourced from bulk-SMS vendors' guides rather than from the NCC directly. The
   direction is certainly right (per-operator registration, CAC required,
   transactional bind for DND, 2–3 weeks) but exact current timelines and
   document lists should be confirmed with whichever provider is chosen.

8. **Zustand v5's TypeScript `create<State>()(...)` curried-call requirement**
   is recorded from prior knowledge, not verified against the v5 changelog in
   this pass. Low risk — it fails loudly at compile time if wrong.

9. **Motion 13's `@emotion/is-prop-valid` removal** is marked probable; it comes
   from a summary of the upgrade guide rather than a direct read of the changelog
   entry. The `LazyMotion`/`m` API itself is **confirmed** directly from
   motion.dev.

10. **Flutterwave's `verif-hash` mechanism** is marked probable — the analysis of
    it being a static, body-independent hash is consistent and technically
    coherent across sources, but `developer.flutterwave.com/docs/webhooks` was
    not read directly. Confirm before building any Flutterwave fallback.

---

## Suggested pinned versions

For the record, as read from the registry on 2026-09-23. Re-read at install time
rather than copying these; that is what the brief asks for and these will drift.

| Package | Version |
| --- | --- |
| `next` | 16.3.6 |
| `react` / `react-dom` | 19.3.0 |
| `typescript` | 7.0.2 |
| `tailwindcss` | 4.3.3 |
| `shadcn` (CLI) | 4.21.0 |
| `radix-ui` | 1.6.7 |
| `@tanstack/react-query` | 5.103.2 |
| `zustand` | 5.0.15 |
| `react-hook-form` | 7.88.0 |
| `@hookform/resolvers` | 5.9.1 |
| `zod` | 4.6.5 |
| `openapi-typescript` | 7.13.0 |
| `@serwist/turbopack` | 9.5.12 |
| `@serwist/next` | 9.5.12 |
| `motion` | 13.4.1 |
| `gsap` | 3.15.0 |
| `lenis` | 1.3.26 |
| `@formkit/auto-animate` | 0.10.0 |
| `lucide-react` | 1.47.0 |
| `@rive-app/react-canvas` | 4.34.3 |
| `@lottiefiles/dotlottie-react` | 0.19.16 |
| `@playwright/test` | 1.63.0 |
| `vitest` | 5.0.1 |
| `axe-core` | 4.13.0 |
| `@lhci/cli` | 0.15.1 |
