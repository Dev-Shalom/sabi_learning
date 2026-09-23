/* Regenerate docs/screenshots/.
 *
 * Phase 2 is a starred phase: the shell has to be *looked at*, in both themes,
 * at 360px and at desktop. That is not ceremony. v1's navigation was
 * unreachable on a phone for a while and the thing that caught it was a person
 * opening a screenshot at 360px; the existing CSS still carries a comment
 * about a gutter bug that was only ever visible that way.
 *
 * A standalone script rather than a spec, because these are a deliverable, not
 * an assertion. A screenshot test that fails on a one-pixel shift teaches
 * everybody to regenerate the baseline without looking, which is the opposite
 * of the point.
 *
 * Needs `next start` on PORT and, for the home page to show real data,
 * FastAPI on 8020. Run:  node tools/screenshots.mjs
 */

import { chromium } from "@playwright/test";
import { mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";

const PORT = process.env.PORT ?? 3100;
const BASE = `http://127.0.0.1:${PORT}`;
// Its own folder. The Jinja surface has screenshots under
// docs/screenshots/ with names that overlap these -- login, signup, home --
// and writing here flattened four of them before this was noticed. Both
// surfaces are live during the migration, so both sets of evidence matter.
const OUT = path.resolve("../docs/screenshots/web");

const PAGES = [
  ["home", "/"],
  ["practice", "/practice"],
  ["exam", "/exam"],
  ["tutor", "/tutor"],
  ["notebook", "/notebook"],
  ["login", "/login"],
  ["signup", "/signup"],
];

const SIZES = [
  // The design case, not an edge case.
  ["360", { width: 360, height: 780 }],
  ["1440", { width: 1440, height: 900 }],
];

const THEMES = ["light", "dark"];

const browser = await chromium.launch();
await mkdir(OUT, { recursive: true });

// Clear first, so a page that has been deleted does not leave a stale image
// behind looking like current evidence.
for (const f of await readdir(OUT).catch(() => [])) {
  if (f.endsWith(".png")) await rm(path.join(OUT, f));
}

let count = 0;
for (const [themeName, colorScheme] of THEMES.map((t) => [t, t])) {
  for (const [sizeName, viewport] of SIZES) {
    const context = await browser.newContext({
      viewport,
      colorScheme,
      deviceScaleFactor: 2,
      reducedMotion: "reduce", // no half-finished transitions in the image
    });
    const page = await context.newPage();

    for (const [name, route] of PAGES) {
      await page.goto(`${BASE}${route}`, { waitUntil: "networkidle" });
      const file = path.join(OUT, `${name}-${sizeName}-${themeName}.png`);
      // The viewport, NOT fullPage. A full-page capture draws `position:
      // fixed` elements at their scroll position, so the first attempt put
      // the tab bar across the middle of the page on top of a heading -- an
      // artefact that looks exactly like a layout bug. These are evidence
      // about a phone screen, so they are a phone screen.
      await page.screenshot({ path: file });
      count++;
    }
    await context.close();
  }
}

await browser.close();
console.log(`wrote ${count} screenshots to docs/screenshots/web/`);
