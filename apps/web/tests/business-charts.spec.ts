import { test, expect } from "@playwright/test";
test("overview shows five real-data business charts and responsive period controls", async ({
  page,
}) => {
  const response = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Chart owner",
      organization_name: "Charts Wholesale",
      email: `charts-${Date.now()}@example.com`,
      password: "Chart-browser-only-123",
    },
  });
  expect(response.status()).toBe(201);
  const org = (await response.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const customer = await (
    await page.request.post("/api/customers", {
      headers,
      data: { name: "Chart customer" },
    })
  ).json();
  const product = await (
    await page.request.post("/api/products", {
      headers,
      data: {
        name: "Chart Rice",
        sku: "CHART-RICE",
        price_minor: 25000,
        cost_minor: 15000,
        reorder_level: 10,
      },
    })
  ).json();
  await page.request.post(`/api/products/${product.id}/stock`, {
    headers,
    data: { delta: 10, reason: "Chart sample stock" },
  });
  const sale = await page.request.post("/api/commerce/sales", {
    headers: { ...headers, "Idempotency-Key": "chart-browser-sale" },
    data: {
      customer_id: customer.id,
      items: [{ product_id: product.id, quantity: 2 }],
      human_confirmed: true,
      expected_total_minor: 50000,
      paid_minor: 50000,
      payment_method: "cash",
    },
  });
  expect(sale.status()).toBe(201);
  await page.goto("/dashboard");
  const charts = page.getByRole("region", {
    name: "Business performance charts",
    exact: true,
  });
  await expect(
    charts.getByRole("region", { name: "Gross profit", exact: true }),
  ).toBeVisible();
  for (const name of [
    "Profit and sales",
    "Low stock items",
    "Top selling products",
    "Staff performance",
  ])
    await expect(
      charts.getByRole("region", { name, exact: true }),
    ).toBeVisible();
  await expect(
    charts
      .getByRole("region", { name: "Gross profit", exact: true })
      .getByText("LKR 200.00", { exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    charts
      .getByRole("region", { name: "Low stock items", exact: true })
      .getByText("Chart Rice", { exact: true }),
  ).toBeVisible();
  await expect(
    charts
      .getByRole("region", { name: "Top selling products", exact: true })
      .getByText("Chart Rice", { exact: true }),
  ).toBeVisible();
  await expect(
    charts
      .getByRole("region", { name: "Staff performance", exact: true })
      .getByText("Chart owner", { exact: true })
      .first(),
  ).toBeVisible();
  await charts.getByLabel("Chart period", { exact: true }).selectOption("7");
  await expect(charts.getByRole("img")).toBeVisible();
  await charts.getByText("View chart data", { exact: true }).click();
  await expect(
    charts.getByRole("columnheader", { name: "Gross profit", exact: true }),
  ).toBeVisible();
  await charts.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/business-charts-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/business-charts-mobile.png",
    fullPage: true,
  });
});
