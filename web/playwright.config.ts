import { defineConfig, devices } from "@playwright/test";

/* The two things the brief makes acceptance criteria for this phase:
 * every section reachable at 360px, and keyboard navigation that works.
 *
 * Both are tested against the real production build rather than the dev
 * server, because the dev server ships different JS and a bundle the student
 * never receives. `npm run build` must have run first; CI does that anyway to
 * measure page weight, so the build is reused rather than repeated.
 *
 * These tests deliberately do NOT need FastAPI running. The layout, the tab
 * bar and the focus behaviour are what is under test, and they render whether
 * the API answers or not -- the home page has an honest "cannot reach its
 * library" panel for exactly that case. Keeping the backend out of it is what
 * makes these tests reliable enough to gate a merge on.
 */

const PORT = 3100;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "list" : "line",

  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },

  projects: [
    {
      // 360px is the design case, not an edge case: it is the width of the
      // cheap Android phones this product is for, and v1 shipped a navigation
      // that was unreachable below 1024px because nobody looked here.
      name: "phone-360",
      use: { ...devices["Pixel 5"], viewport: { width: 360, height: 640 } },
    },
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],

  webServer: {
    command: `npx next start -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
