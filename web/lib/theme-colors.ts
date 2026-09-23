/* The one place outside `web/styles/tokens.css` where a colour may be written.
 *
 * It exists because of a real gap, not as an escape hatch. Next's `themeColor`
 * viewport metadata becomes a `<meta name="theme-color">` tag that the browser
 * reads to paint the address bar and the PWA status bar. That happens before
 * and outside the stylesheet, so it cannot be `var(--paper)` -- a CSS custom
 * property is meaningless in a meta tag, and the browser would ignore it and
 * fall back to white, which is exactly the wrong colour in dark mode.
 *
 * So the value has to be duplicated. The duplication is made safe rather than
 * forbidden: `tools/contrast_web.py` reads this file and fails if either value
 * stops matching `--paper` in the theme it claims. Two places, one truth,
 * enforced -- rather than one place and a broken status bar.
 *
 * Nothing else belongs here. Every other colour in the app is a token, used
 * through Tailwind or `var()`.
 */

/** `--paper` in the light theme. Must equal `:root { --paper }`. */
export const PAPER_LIGHT = "#F7F9FB";

/** `--paper` in the dark theme. Must equal the dark block's `--paper`. */
export const PAPER_DARK = "#0E1B2A";
