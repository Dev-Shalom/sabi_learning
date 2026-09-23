import { test, expect, type Page } from "@playwright/test";

/** Our error message, not Next's route announcer.
 *
 * Next renders a permanently-mounted `<div role="alert">` to announce route
 * changes, so a bare `getByRole("alert")` matches two elements and fails
 * strict mode. Scoped to the form so the test is about our message. */
const alertOf = (page: Page) => page.locator('form [role="alert"]');

/* The auth pages, tested for the things a build cannot prove.
 *
 * Deliberately not tested here: whether the credentials are correct. That is
 * `tests/test_api_auth.py`, against a real database, and duplicating it in a
 * browser would be slower and would prove less. What these cover is the part
 * that only exists in the rendered page — labels joined to inputs, a failure
 * that reaches a screen reader, and a form a keyboard can drive.
 *
 * FastAPI is not running, so every submission fails. That is the point: the
 * failure path is the one most likely to ship broken, because it is the one
 * nobody clicks through by hand.
 */

for (const [path, heading] of [
  ["/login", /welcome back/i],
  ["/signup", /create your account/i],
] as const) {
  test.describe(path, () => {
    test("has one heading and both fields properly labelled", async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);

      // getByLabel only finds these if the label is really joined to the
      // input, which is the whole assertion.
      await expect(page.getByLabel("Email")).toBeVisible();
      await expect(page.getByLabel("Password")).toBeVisible();
    });

    test("the browser can fill it in", async ({ page }) => {
      await page.goto(path);
      // Without these a password manager cannot offer to save or fill, and a
      // student on a shared phone types their password in by hand every time.
      await expect(page.getByLabel("Email")).toHaveAttribute(
        "autocomplete",
        "email",
      );
      await expect(page.getByLabel("Password")).toHaveAttribute(
        "autocomplete",
        path === "/signup" ? "new-password" : "current-password",
      );
    });

    test("can be filled and submitted from the keyboard alone", async ({
      page,
    }) => {
      await page.goto(path);

      await page.getByLabel("Email").focus();
      await page.keyboard.type("someone@example.test");
      await page.keyboard.press("Tab");
      await page.keyboard.type("a-long-enough-password-2026");
      // Enter inside a form submits it. This is why it is a real <form> and
      // not a div with a click handler.
      await page.keyboard.press("Enter");

      await expect(alertOf(page)).toBeVisible();
    });

    test("a failure is announced, and says nothing was lost", async ({ page }) => {
      await page.goto(path);
      await page.getByLabel("Email").fill("someone@example.test");
      await page.getByLabel("Password").fill("a-long-enough-password-2026");
      await page.getByRole("button", { name: /log in|create account/i }).click();

      const alert = alertOf(page);
      await expect(alert).toBeVisible();

      // role="alert" alone is not enough in every screen reader, so focus is
      // moved to the message. A student who submits and hears nothing has no
      // way to know the form did anything.
      await expect(alert).toBeFocused();

      // The word as well as the colour.
      await expect(alert).toContainText(/problem/i);
      // Nothing you did was wrong, and nothing you typed is gone.
      await expect(alert).toContainText(/try again|lost/i);
    });

    test("the email typed is still there after a failure", async ({ page }) => {
      await page.goto(path);
      await page.getByLabel("Email").fill("typed@example.test");
      await page.getByLabel("Password").fill("a-long-enough-password-2026");
      await page.getByRole("button", { name: /log in|create account/i }).click();

      await expect(alertOf(page)).toBeVisible();
      // Retyping an address on a phone because the server was busy is the
      // kind of small insult that makes people give up.
      await expect(page.getByLabel("Email")).toHaveValue("typed@example.test");
    });

    test("each page offers the other", async ({ page }) => {
      await page.goto(path);
      const other = path === "/login" ? "/signup" : "/login";
      await page.getByRole("link", { name: /create an account|log in/i }).click();
      await expect(page).toHaveURL(new RegExp(other));
    });
  });
}
