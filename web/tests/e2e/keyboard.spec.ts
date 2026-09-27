import { test, expect } from "@playwright/test";

/* Keyboard navigation is an acceptance criterion for this phase, and it is
 * not a box-ticking one. The JAMB simulator is driven entirely from the
 * keyboard -- JAMB's own manual documents A/B/C/D to select, N or the right
 * arrow for next, P or the left arrow for previous, S to submit -- so a
 * student who has practised on Sabi must find the same keys working. A focus
 * ring that cannot be seen, or a tab order that skips the navigation, breaks
 * that before the exam UI is even written.
 */

test("the skip link is the first thing a keyboard reaches", async ({ page }) => {
  await page.goto("/dashboard");
  await page.keyboard.press("Tab");

  const focused = page.locator(":focus");
  await expect(focused).toHaveText(/skip to content/i);

  // And it must work, not merely exist.
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("every section can be reached and opened without a mouse", async ({
  page,
}) => {
  await page.goto("/dashboard");

  // Walk forward with Tab until the Practice tab has focus, then open it with
  // Enter. A bounded walk rather than a fixed count, because the number of
  // focusable things on the page will change as the product grows and a
  // hardcoded count would turn into a false failure.
  let reached = false;
  for (let i = 0; i < 40 && !reached; i++) {
    await page.keyboard.press("Tab");
    const label = await page.locator(":focus").textContent();
    if (label?.trim() === "Practice") reached = true;
  }

  expect(reached, "Practice was never reached by tabbing").toBe(true);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/practice/);
});

test("focus is always visible", async ({ page }) => {
  await page.goto("/dashboard");

  const nav = page.getByRole("navigation", { name: "Sections" });
  const link = nav.getByRole("link", { name: "Tutor", exact: true });
  await link.focus();

  const ring = await link.evaluate((el) => {
    const s = getComputedStyle(el);
    return {
      outlineStyle: s.outlineStyle,
      outlineWidth: parseFloat(s.outlineWidth),
      outlineColor: s.outlineColor,
    };
  });

  // `outline: none` with nothing in its place is the single most common way a
  // keyboard user is locked out of a site, so it is asserted rather than
  // trusted to a code review.
  expect(ring.outlineStyle).not.toBe("none");
  expect(ring.outlineWidth).toBeGreaterThanOrEqual(2);
});

test("a keyboard user is never trapped", async ({ page }) => {
  await page.goto("/dashboard");

  // Tab all the way round. If focus never returns to the document body or the
  // first element, something is holding it -- which on an exam screen would
  // mean a student cannot leave a question.
  const seen = new Set<string>();
  for (let i = 0; i < 50; i++) {
    await page.keyboard.press("Tab");
    const id = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return "body";
      return `${el.tagName}:${(el.textContent ?? "").trim().slice(0, 20)}`;
    });
    if (seen.has(id)) return; // came back round: not trapped
    seen.add(id);
  }

  throw new Error("focus never cycled: a keyboard user may be trapped");
});
