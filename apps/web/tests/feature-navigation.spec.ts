import { test, expect } from "@playwright/test";
test("existing tools are directly accessible and products survive an analytics failure", async ({
  page,
}) => {
  const reg = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Navigation owner",
      organization_name: "Navigation Wholesale",
      email: `navigation-${Date.now()}@example.com`,
      password: "Navigation-only-test-123",
    },
  });
  expect(reg.status()).toBe(201);
  const org = (await reg.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  for (let i = 0; i < 55; i++) {
    const r = await page.request.post("/api/products", {
      headers,
      data: {
        name: `Product ${String(i).padStart(3, "0")}`,
        sku: `SKU-${String(i).padStart(3, "0")}`,
        barcode: `BAR${String(i).padStart(3, "0")}`,
        price_minor: 25000,
      },
    });
    expect(r.status()).toBe(201);
  }
  await page.route("**/api/analytics", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Analytics temporarily unavailable" }),
    }),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByRole("region", { name: "Workspace tools" }),
  ).toBeVisible();
  for (const name of [
    "Open POS",
    "Open Purchases",
    "Open Warehouses",
    "Open Returns",
    "Open Credit & payments",
    "Open Reports & expenses",
    "Open Delivery",
    "Open Team",
  ])
    await expect(
      page.getByRole("navigation").getByRole("button", { name, exact: true }),
    ).toHaveCount(1);
  await page
    .getByRole("button", { name: "Products & inventory", exact: true })
    .click();
  await expect(
    page.getByRole("cell", { name: "SKU-000", exact: true }),
  ).toBeVisible({ timeout: 20000 });
  await expect(page.locator("tbody tr")).toHaveCount(50);
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Analytics temporarily unavailable" }),
  ).toContainText("Analytics temporarily unavailable");
  await page
    .getByRole("button", { name: "Next products", exact: true })
    .click();
  await expect(
    page.getByRole("cell", { name: "SKU-054", exact: true }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(5);
  await page.getByLabel("Search inventory").fill("BAR054");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Open Purchases", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "Purchases", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(
    page.getByRole("tab", { name: "Purchases", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("heading", { name: "Create purchase order", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Open Reports & expenses", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Sales & profit reports" }),
  ).toBeVisible();
  expect(
    (
      await page.request.put("/api/dashboard-preferences", {
        headers,
        data: { modules: ["orders", "customers"] },
      })
    ).status(),
  ).toBe(200);
  await page.reload();
  const enabledCatalog = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/dashboard-preferences") &&
      r.request().method() === "PUT",
    { timeout: 20000 },
  );
  await page
    .getByRole("button", { name: "Products & inventory", exact: true })
    .click();
  expect((await enabledCatalog).status()).toBe(200);
  await expect(
    page.getByRole("cell", { name: "SKU-000", exact: true }),
  ).toBeVisible({ timeout: 20000 });
  expect(
    (
      await (
        await page.request.get("/api/dashboard-preferences", { headers })
      ).json()
    ).modules,
  ).toContain("catalog");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
});
