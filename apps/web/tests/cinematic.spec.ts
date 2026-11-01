import { test, expect } from "@playwright/test";
test.use({ actionTimeout: 15000 });

test("cinematic marketing, honest demo, navigation and application entry points", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Your Business. One Intelligent Platform.",
  );
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  const brokenAnchors = await page
    .locator('a[href^="#"]')
    .evaluateAll((links) =>
      links
        .map((link) => link.getAttribute("href")!)
        .filter((href) => !document.getElementById(href.slice(1))),
    );
  expect(brokenAnchors).toEqual([]);
  await page.screenshot({
    caret: "initial",
    path: "test-results/cinematic-desktop-hero.png",
  });
  await page.getByRole("link", { name: "Explore Features" }).click();
  await page.locator("#demo").scrollIntoViewIfNeeded();
  const demo = page.locator("#demo");
  await demo.getByRole("button", { name: "Organize message" }).click();
  await expect(
    demo.getByRole("heading", { name: "A draft, ready for your review." }),
  ).toBeVisible();
  await expect(demo.locator(".om-extraction-fields")).toContainText(
    "Black T-shirt",
  );
  await expect(demo.locator(".om-extraction-fields")).toContainText(
    /Quantity\s*2/,
  );
  await demo.getByRole("button", { name: "Confirm example only" }).click();
  await expect(
    demo.getByText(
      "Simulation complete. No order was saved and no reply was sent.",
    ),
  ).toBeVisible();
  await demo.locator(".om-example-choices button").nth(2).click();
  await demo.getByRole("button", { name: "Organize message" }).click();
  await expect(demo.locator(".om-extraction-fields")).toContainText("Rice bag");
  await expect(demo.locator(".om-extraction-fields")).toContainText(
    /Quantity\s*2/,
  );
  await demo
    .getByLabel("Your example customer message")
    .fill("Something outside the sample catalog");
  await demo.getByRole("button", { name: "Organize message" }).click();
  await expect(
    demo.getByRole("heading", { name: "This needs a human look." }),
  ).toBeVisible();
  await expect(
    demo.getByRole("button", { name: "Confirm example only" }),
  ).toHaveCount(0);
  await demo.getByLabel("Your example customer message").fill(" ");
  await expect(
    demo.getByRole("button", { name: "Organize message" }),
  ).toBeDisabled();
  await page.locator("#how-it-works").scrollIntoViewIfNeeded();
  await page
    .getByRole("button", { name: "Workflow step 3", exact: true })
    .click();
  await expect(page.getByText("Your confirmation is required.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Workflow step 5", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Workflow step 5", exact: true })
    .click();
  await expect(page.getByText("Your business, at a glance.")).toBeVisible();
  const dashboard = page.locator("#dashboard-preview");
  await dashboard.getByRole("button", { name: "Preview orders" }).click();
  await dashboard
    .getByRole("button", { name: "Completed", exact: true })
    .click();
  await expect(dashboard.locator(".om-table-row")).toHaveCount(1);
  await expect(dashboard.locator(".om-table-row")).toContainText(
    "Amaya Fernando",
  );
  await dashboard.getByRole("button", { name: "Preview customers" }).click();
  await expect(dashboard.locator(".om-customer-list>div")).toHaveCount(3);
  await dashboard
    .getByRole("button", { name: "Preview conversations" })
    .click();
  await expect(dashboard.getByText("Draft ready for review")).toBeVisible();
  await dashboard.getByRole("button", { name: "Preview overview" }).click();
  await page
    .getByRole("button", { name: "Beauty", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Beauty wholesale, organized.",
    }),
  ).toBeVisible();
  await page
    .locator("#questions summary")
    .filter({ hasText: "Can customers write in Sinhala" })
    .click();
  await expect(page.locator("#questions details[open]")).toContainText(
    "human review",
  );
  await expect(page.locator("#pricing")).toContainText("7,400");
  await expect(page.locator("#pricing")).toContainText("500 orders / month");
  await expect(
    page.locator("#pricing").getByText("Coming later", { exact: false }),
  ).toHaveCount(2);
  await page.getByRole("button", { name: "Pause motion", exact: true }).click();
  await expect(page.locator(".om")).toHaveClass(/om-paused/);
  await page.screenshot({
    caret: "initial",
    path: "test-results/cinematic-desktop-full.png",
    fullPage: true,
  });
  for (const [width, height, label] of [
    [768, 1024, "tablet"],
    [390, 844, "mobile"],
    [320, 740, "small-mobile"],
  ] as const) {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Pricing", exact: true })
      .click();
    await expect(page).toHaveURL(/#pricing$/);
    await expect(
      page.getByRole("button", { name: "Open navigation" }),
    ).toBeVisible();
    await page.goto("/");
    await page.screenshot({
      caret: "initial",
      path: `test-results/cinematic-${label}.png`,
      fullPage: true,
    });
  }
  await page
    .getByRole("link", { name: "Get Started", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/sign-up$/);
  await expect(page.getByLabel("Business name")).toBeVisible();
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in$/);
  for (const path of ["privacy", "terms"]) {
    const response = await page.goto(`/${path}`);
    expect(response?.status()).toBe(200);
    await expect(
      page.getByText(/not yet been supplied for publication/),
    ).toBeVisible();
    await page.getByRole("link", { name: "Back to OrderMesh" }).click();
    await expect(page).toHaveURL(/\/$/);
  }
  expect(errors).toEqual([]);
});

test("product film advances, pauses and respects reduced motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.locator(".om-cinema").scrollIntoViewIfNeeded();
  const current = page.locator(".om-film-dots button[aria-pressed=true]");
  const first = await current.getAttribute("aria-label");
  await expect.poll(() => current.getAttribute("aria-label")).not.toBe(first);
  await page.getByRole("button", { name: "Pause product sequence" }).click();
  const stopped = await current.getAttribute("aria-label");
  await page.waitForTimeout(2500);
  expect(await current.getAttribute("aria-label")).toBe(stopped);
  await page
    .getByRole("button", { name: "Show scene 3: An order draft takes shape" })
    .click();
  await expect(page.locator(".om-extracted")).toHaveClass(/shown/);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByRole("button", { name: "Play product sequence" }).click();
  await page.waitForTimeout(2500);
  await expect(current).toHaveAttribute(
    "aria-label",
    "Show scene 3: An order draft takes shape",
  );
  expect(
    await page
      .locator(".om-phone-position")
      .evaluate((el) => getComputedStyle(el).animationName),
  ).toBe("none");
});
