import { test, expect } from "@playwright/test";

test("owner sees WhatsApp approval notification, confirms stock once and controls chatbot", async ({
  page,
}) => {
  const registered = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Approval owner",
      organization_name: "Approval Distributors",
      email: `approval-${Date.now()}@example.com`,
      password: "Approval-test-password-123",
    },
  });
  expect(registered.status()).toBe(201);
  const org = (await registered.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const customer = await (
    await page.request.post("/api/customers", {
      headers,
      data: { name: "Trade Stores", phone: "+94770001122" },
    })
  ).json();
  const product = await (
    await page.request.post("/api/products", {
      headers,
      data: {
        name: "Rice",
        sku: "RICE-APPROVE",
        category: "grocery",
        price_minor: 25000,
        unit: "bags",
      },
    })
  ).json();
  expect(
    (
      await page.request.post(`/api/products/${product.id}/stock`, {
        headers,
        data: { delta: 10, reason: "Opening stock" },
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await page.request.post("/api/inbox/phone-numbers", {
        headers,
        data: {
          phone_number_id: "934567890123456",
          display_phone_number: "+94770001111",
        },
      })
    ).status(),
  ).toBe(201);
  async function incoming(text: string) {
    const result = await page.request.post("/api/inbox/simulator", {
      headers,
      data: {
        phone_number_id: "934567890123456",
        customer_phone: "+94770001122",
        customer_name: "Trade Stores",
        text,
      },
    });
    expect(result.status()).toBe(201);
  }
  await incoming("Rice 2");
  let products = await (
    await page.request.get("/api/products", { headers })
  ).json();
  expect(products[0].stock).toBe(10);
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Open Orders", exact: true })
    .first()
    .click();
  const pending = page.getByRole("region", {
    name: "WhatsApp orders awaiting approval",
  });
  await expect(pending).toBeVisible();
  await expect(
    pending.getByText("Simulator request", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/whatsapp-pending-approval.png",
    fullPage: true,
  });
  await pending.getByRole("button", { name: "Review and approve" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Customer", { exact: true })
    .selectOption(customer.id);
  await dialog
    .getByLabel("I reviewed all extraction flags", { exact: false })
    .check();
  await dialog
    .getByLabel("I have checked the customer", { exact: false })
    .check();
  await dialog.getByRole("button", { name: "Confirm & create order" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(pending).not.toBeVisible();
  products = await (
    await page.request.get("/api/products", { headers })
  ).json();
  expect(products[0].stock).toBe(8);
  expect(
    (await (await page.request.get("/api/orders", { headers })).json()).length,
  ).toBe(1);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Activate WhatsApp chatbot", { exact: true }).check();
  await page.getByRole("button", { name: "Save chatbot settings" }).click();
  await expect(
    page.getByText("WhatsApp chatbot activated.", { exact: false }),
  ).toBeVisible();
  expect(
    (
      await (
        await page.request.get("/api/inbox/chatbot-settings", { headers })
      ).json()
    ).enabled,
  ).toBe(true);
  await incoming("Rice 100");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Open Orders", exact: true })
    .first()
    .click();
  await expect(
    pending.getByText("insufficient stock", { exact: true }),
  ).toBeVisible();
  page.once("dialog", (confirmation) => confirmation.accept());
  await pending.getByRole("button", { name: "Reject request" }).click();
  await expect(pending).not.toBeVisible();
  products = await (
    await page.request.get("/api/products", { headers })
  ).json();
  expect(products[0].stock).toBe(8);
  expect(
    (
      await (
        await page.request.get("/api/inbox/chatbot-replies", { headers })
      ).json()
    ).length,
  ).toBe(0);
});
