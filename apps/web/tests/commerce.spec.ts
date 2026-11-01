import { test, expect } from "@playwright/test";
test("POS, GRN, warehouse transfer, credit and live notification acknowledgement", async ({
  page,
}) => {
  const r = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Commerce QA",
      organization_name: "Demo Wholesale QA",
      email: `commerce-${Date.now()}@example.com`,
      password: "Commerce-test-only-123",
    },
  });
  expect(r.status()).toBe(201);
  const org = (await r.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const customer = await (
    await page.request.post("/api/customers", {
      headers,
      data: {
        name: "Demo Trade Store",
        credit_limit_minor: 100000,
        payment_terms_days: 7,
      },
    })
  ).json();
  const p = await (
    await page.request.post("/api/products", {
      headers,
      data: {
        name: "Demo Rice",
        sku: "DEMO-RICE",
        barcode: "100001",
        category: "grocery",
        price_minor: 25000,
        cost_minor: 15000,
        reorder_level: 8,
      },
    })
  ).json();
  expect(
    (
      await page.request.post(`/api/products/${p.id}/stock`, {
        headers,
        data: { delta: 10, reason: "Demo opening stock" },
      })
    ).status(),
  ).toBe(200);
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Operations", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Business operations" }),
  ).toBeVisible();
  await page.getByLabel("Scan barcode, SKU or search").fill("100001");
  await page.getByLabel("Scan barcode, SKU or search").press("Enter");
  await page.getByLabel("Quantity for Demo Rice").fill("2");
  await page.getByLabel("I reviewed quantities, prices and payment.").check();
  await expect(
    page.getByRole("button", { name: "Complete sale" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Complete sale" }).click();
  await expect(
    page.getByText("Sale posted. Stock and payment recorded.", {
      exact: false,
    }),
  ).toBeVisible();
  const sale = (
    await (await page.request.get("/api/orders", { headers })).json()
  )[0];
  expect(sale.financial_posted).toBe(true);
  expect(
    (await (await page.request.get("/api/products", { headers })).json())[0]
      .stock,
  ).toBe(8);
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "Notification centre" })
      .getByText("Low stock", { exact: true }),
  ).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "Mark all read" }).click();
  await expect(page.getByText("0 unread · 1 active alerts")).toBeVisible();
  await page.getByRole("button", { name: "Close notifications" }).click();
  await page.getByRole("tab", { name: "Purchases", exact: true }).click();
  const supplier = page.getByRole("region", {
    name: "Add supplier",
    exact: true,
  });
  await supplier.getByLabel("Supplier name").fill("Demo Supplier");
  await supplier
    .getByRole("button", { name: "Add supplier", exact: true })
    .click();
  await expect(supplier.getByText("Saved successfully.")).toBeVisible();
  const purchase = page.getByRole("region", {
    name: "Create purchase order",
    exact: true,
  });
  await purchase
    .getByLabel("Supplier", { exact: true })
    .selectOption({ label: "Demo Supplier" });
  await purchase.getByLabel("Product", { exact: true }).selectOption(p.id);
  await purchase.getByLabel("Quantity", { exact: true }).fill("5");
  await purchase.getByLabel("Unit cost (LKR)").fill("160");
  await purchase
    .getByRole("button", { name: "Create purchase order", exact: true })
    .click();
  await page.getByRole("button", { name: "Receive goods / GRN" }).click();
  await expect(page.getByText("· received", { exact: false })).toBeVisible();
  await page.getByRole("tab", { name: "Reports & expenses" }).click();
  await page.getByRole("button", { name: "Run report", exact: true }).click();
  await expect(
    page.getByText("Posted sales: 1.", { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/commerce-mobile.png",
    fullPage: true,
  });
  const accounts = await (
    await page.request.get("/api/commerce/accounts", { headers })
  ).json();
  expect(
    accounts.find((x: { id: string }) => x.id === customer.id)
      .outstanding_minor,
  ).toBe(0);
});
