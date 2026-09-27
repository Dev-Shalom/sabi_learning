import { test, expect } from "@playwright/test";

/* The test v1 did not have.
 *
 * v1 put every section in a masthead hidden below 1024px and left nothing in
 * its place, so Practice and the Notebook were simply unreachable on a phone
 * -- on a product whose entire audience is on phones. It was caught by a
 * person looking at a screenshot, which is not a thing that happens reliably.
 *
 * So reachability is asserted, at the width it broke at.
 */

const SECTIONS = [
  { label: "Home", path: "/dashboard" },
  { label: "Practice", path: "/practice" },
  { label: "Mocks", path: "/exam" },
  { label: "Tutor", path: "/tutor" },
  { label: "Saved", path: "/notebook" },
];

test.describe("every section is reachable", () => {
  for (const { label, path } of SECTIONS) {
    test(`${label} can be reached from the home screen`, async ({ page }) => {
      await page.goto("/dashboard");

      const nav = page.getByRole("navigation", { name: "Sections" });
      const link = nav.getByRole("link", { name: label, exact: true });

      // Present, and actually hittable: a link that exists but sits under
      // something else, or off-screen, is not reachable.
      await expect(link).toBeVisible();
      await link.click();

      await expect(page).toHaveURL(new RegExp(`${path === "/" ? "/$" : path}`));
    });
  }
});

test("the tab bar names every section in words, not icons alone", async ({
  page,
}) => {
  await page.goto("/dashboard");
  const nav = page.getByRole("navigation", { name: "Sections" });

  for (const { label } of SECTIONS) {
    // An icon on its own is a guess, and this audience should not have to
    // guess where the mocks are.
    await expect(nav.getByText(label, { exact: true })).toBeVisible();
  }
});

test("nothing forces the page sideways", async ({ page }, testInfo) => {
  await page.goto("/dashboard");

  // A horizontal scrollbar at 360px means something is wider than the phone,
  // and the student reads the question by dragging. Checked on the real
  // layout rather than by eye.
  const overflow = await page.evaluate(() => {
    const d = document.documentElement;
    return { scroll: d.scrollWidth, client: d.clientWidth };
  });

  expect(
    overflow.scroll,
    `page scrolls sideways at ${testInfo.project.use.viewport?.width}px`,
  ).toBeLessThanOrEqual(overflow.client + 1);
});

test("every tab is a thumb-sized target", async ({ page }) => {
  await page.goto("/dashboard");
  const nav = page.getByRole("navigation", { name: "Sections" });

  for (const { label } of SECTIONS) {
    const box = await nav
      .getByRole("link", { name: label, exact: true })
      .boundingBox();

    expect(box, `${label} has no box`).not.toBeNull();
    // 44px is the floor. The design case is a student tapping with a thumb on
    // a moving bus, not a mouse pointer.
    expect(box!.height, `${label} is ${box!.height}px tall`).toBeGreaterThanOrEqual(44);
    expect(box!.width, `${label} is ${box!.width}px wide`).toBeGreaterThanOrEqual(44);
  }
});

test("the current section is marked for a screen reader, not only in colour", async ({
  page,
}) => {
  await page.goto("/practice");
  const nav = page.getByRole("navigation", { name: "Sections" });

  // Roughly one student in twelve cannot tell the green from the grey, so
  // "which tab am I on" cannot be carried by colour alone.
  await expect(
    nav.getByRole("link", { name: "Practice", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});
