import { test, expect } from "@playwright/test";
for (const width of [1440, 390])
  test(`shared design remains usable at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 960 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    async function capture(name: string) {
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth + 1,
          ),
        )
        .toBe(true);
      const heading = page.locator("h1").first();
      if (await heading.count())
        expect(
          await heading.evaluate((el) =>
            parseFloat(getComputedStyle(el).fontSize),
          ),
        ).toBeGreaterThanOrEqual(25);
      await page.screenshot({
        path: testInfo.outputPath(`${name}.png`),
        fullPage: true,
        caret: "initial",
      });
    }
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Your Business.",
    );
    await capture("home");
    await page.goto("/sign-in");
    await expect(
      page.getByRole("heading", { name: "Welcome back" }),
    ).toBeVisible();
    await capture("sign-in");
    await page.goto("/sign-up");
    await capture("sign-up");
    await page.getByLabel("Your name", { exact: true }).fill("Design Reviewer");
    await page.getByLabel("Business name").fill("Design Review Workspace");
    await page
      .getByLabel("Email address")
      .fill(`design-${width}-${Date.now()}@example.com`);
    await page.getByLabel(/^Password/).fill("Design-review-password-123");
    await page
      .getByRole("button", { name: "Create workspace", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Business at a glance" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Sales trend" }),
    ).toBeVisible();
    await expect(
      page.getByRole("img", { name: /Sales trend over the last seven days/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Order status" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Review WhatsApp orders/ }),
    ).toBeVisible();
    await expect
      .poll(() =>
        page
          .locator(".insight-panel")
          .first()
          .evaluate((el) => parseFloat(getComputedStyle(el).paddingLeft)),
      )
      .toBeGreaterThanOrEqual(16);
    await capture("dashboard");
    await page.goto("/dashboard/inbox");
    await expect(
      page.getByRole("heading", { name: "Connect your WhatsApp" }),
    ).toBeVisible();
    await capture("inbox");
    expect(errors).toEqual([]);
  });
