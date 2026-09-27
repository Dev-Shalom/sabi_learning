"use client";

import { LazyMotion, MotionConfig } from "motion/react";

const loadFeatures = () => import("@/lib/motion-features").then((m) => m.default);

/* Motion, loaded the budgeted way (v2 §6.2).
 *
 * `LazyMotion` with `domAnimation` ships animations, variants, exit and
 * gestures, and leaves out drag and layout projection. Loaded as a function,
 * so those features arrive in their own chunk after hydration: measured, the
 * eager version put every route ~40 KB over its 150 KB first-load budget.
 * Until the chunk lands an `m.*` element renders in its final state, which is
 * the right fallback -- nothing is hidden waiting for an animation. `strict`
 * makes importing the full `motion` component a runtime error, so a feature
 * cannot quietly pull the whole library into a route with a 150 KB budget:
 * use `m.div` from "motion/react-m", not `motion.div`.
 *
 * A feature that genuinely needs drag or `layout` (the exam grid does not; a
 * swipeable card might) wraps its own subtree in
 * `<LazyMotion features={domMax}>` so only that route pays for it.
 *
 * `reducedMotion="user"` makes every Motion animation respect the OS setting:
 * transforms are dropped and opacity kept, which is the behaviour the design
 * brief asks for (fewer, gentler, not none).
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}
