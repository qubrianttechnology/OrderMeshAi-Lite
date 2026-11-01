import { test, expect } from "@playwright/test";
test("Google login starts even before client JavaScript loads", async ({
  browser,
  baseURL,
}) => {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    baseURL,
  });
  try {
    const page = await context.newPage();
    await page.route("**/api/auth/google/start?intent=sign-in", (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/plain",
        body: "Google login route reached",
      }),
    );
    await page.goto("/sign-in");
    await page
      .getByRole("link", { name: "Continue with Google", exact: true })
      .click();
    await expect(page.locator("body")).toHaveText("Google login route reached");
  } finally {
    await context.close();
  }
});
