/* The motion vocabulary, for JavaScript.
 *
 * The same curves and durations as the CSS tokens in styles/tokens.css, so a
 * Motion-driven element and a CSS-transitioned one move as one product. A
 * component that needs a curve imports it from here; it does not invent one.
 * docs/DESIGN.md says which to reach for when.
 *
 * Two rules from the design brief are enforced by what is (not) here:
 *   - no ease-in for anything the student is watching arrive;
 *   - nothing between a key press in exam mode and the answer being saved.
 *     There is deliberately no "exam" preset.
 */

/** Cubic-bezier control points, matching the CSS custom properties. */
export const EASE = {
  /** --ease. Decelerate hard and settle flat. The workhorse for arrivals. */
  out: [0.32, 0.72, 0, 1] as const,
  /** Strong ease-out for small UI responses (a popover, a toast). */
  snap: [0.23, 1, 0.32, 1] as const,
  /** On-screen movement from one place to another. */
  inOut: [0.77, 0, 0.175, 1] as const,
  /** --ease-exit. Leaving only. */
  exit: [0.4, 0, 1, 1] as const,
};

/** Seconds, because Motion takes seconds. Mirrors --t-* in tokens.css. */
export const DUR = {
  tap: 0.1,
  fast: 0.18,
  mid: 0.28,
  slow: 0.42,
  deal: 0.56,
};

/** Springs, for things with weight or that a finger can interrupt.
 * Apple-style parameters (duration + bounce) because they are the easiest to
 * reason about; bounce stays at or under 0.2 everywhere a student reads. */
export const SPRING = {
  /** A control settling: a tab indicator, a selected option's mark. */
  snappy: { type: "spring", duration: 0.35, bounce: 0.12 } as const,
  /** A card or sheet with physical presence: the deck, a bottom sheet. */
  soft: { type: "spring", duration: 0.55, bounce: 0.18 } as const,
  /** A moment worth a little play: finishing a set, the result number. */
  lively: { type: "spring", duration: 0.7, bounce: 0.28 } as const,
};

/** Delay between siblings arriving together. Short: stagger is decoration and
 * must never hold a student back from tapping. */
export const STAGGER = 0.05;

/** The standard arrival: a few pixels and an opacity, never from scale(0). */
export const rise = {
  initial: { opacity: 0, transform: "translateY(10px)" },
  animate: { opacity: 1, transform: "translateY(0px)" },
  transition: { duration: DUR.slow, ease: EASE.out },
} as const;
