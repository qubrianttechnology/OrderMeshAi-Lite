import { test, expect } from "@playwright/test";

test("register, catalog, Sinhala extraction, confirmation, invoice and mobile layout", async ({
  page,
}) => {
  await page.goto("/sign-up");
  await page.getByLabel("Your name", { exact: true }).fill("QA Owner");
  await page.getByLabel("Business name").fill("QA Distributors");
  await page.getByLabel("Email address").fill(`qa-${Date.now()}@example.com`);
  await page.getByLabel(/^Password/).fill("Browser-test-password-123");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Business at a glance" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "0722 616 616" }),
  ).toHaveAttribute("href", "tel:+94722616616");
  await expect(
    page.getByRole("link", { name: "info@ordermesh.com" }),
  ).toHaveAttribute("href", "mailto:info@ordermesh.com");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/sidebar-collapsed/);
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await expect(page.locator(".app-shell")).toHaveAttribute(
    "data-theme",
    "light",
  );
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await expect(page.locator(".app-shell")).toHaveAttribute(
    "data-theme",
    "dark",
  );
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(page.locator(".app-shell")).toHaveAttribute(
    "data-theme",
    "light",
  );
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Notification centre" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close notifications" }).click();
  await page.getByRole("button", { name: "Customers", exact: true }).click();
  await page.getByRole("button", { name: "Add customer", exact: true }).click();
  await page.getByLabel("Customer name").fill("Perera Stores");
  await page.getByLabel("Phone", { exact: true }).fill("0112345678");
  await page.getByLabel("Address", { exact: true }).fill("Colombo");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Perera Stores", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Products & inventory", exact: true })
    .click();
  await page.getByRole("button", { name: "Add product", exact: true }).click();
  await page.getByLabel("Product name").fill("Rice");
  await page.getByLabel("SKU", { exact: true }).fill("RICE-001");
  await page.getByLabel("Unit price (LKR)").fill("250");
  await page.getByLabel("Product aliases / part numbers").fill("හාල්, සහල්");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.getByRole("button", { name: "Adjust stock", exact: true }).click();
  await page.getByLabel("Quantity change").fill("20");
  await page.getByLabel("Reason for adjustment").fill("Opening stock");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("cell", { name: "20 units" })).toBeVisible();
  await page
    .getByRole("button", { name: "Order assistant", exact: true })
    .click();
  await page.getByLabel("Order message").fill("හාල් 2");
  await page.getByRole("button", { name: "Extract order details" }).click();
  await expect(page.getByText("Draft only · no order created")).toBeVisible();
  await page
    .getByRole("button", { name: "Review & confirm", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Confirm & create order" }),
  ).toBeDisabled();
  await page
    .getByLabel("Customer", { exact: true })
    .selectOption({ label: "Perera Stores" });
  await page.getByLabel("I reviewed all extraction flags").check();
  await page.getByLabel("I have checked the customer").check();
  await page.getByRole("button", { name: "Confirm & create order" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: /^Orders/ }).click();
  await expect(page.getByText("Perera Stores", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /Download invoice/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^invoice-.*\.pdf$/);
  await page.getByRole("button", { name: "Fulfill", exact: true }).click();
  await expect(page.getByText("Fulfilled", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Business at a glance" }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Open menu" }).click();
  await page
    .getByRole("button", { name: "Products & inventory", exact: true })
    .click();
  await expect(page.getByRole("cell", { name: "18 units" })).toBeVisible();
  await page.screenshot({
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open menu" }).click();
  await page
    .getByRole("button", { name: "WhatsApp inbox", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "WhatsApp inbox" }),
  ).toBeVisible();
  await expect(page.getByText("Database: sqlite")).toBeVisible();
  await expect(
    page.getByText(
      "Configuration only; this does not contact Meta or the AI provider.",
    ),
  ).toBeVisible();
  await page.getByText("Developer testing tools", { exact: true }).click();
  await page.getByLabel("Meta phone number ID").fill("123456789012345");
  await page.getByLabel("Display number").fill("+94722616616");
  await page.getByRole("button", { name: "Register number" }).click();
  await expect(
    page.getByText("WhatsApp phone number registered."),
  ).toBeVisible();
  await page
    .getByLabel("Registered phone number")
    .selectOption("123456789012345");
  await page.getByLabel("Customer phone").fill("+94770001122");
  await page.getByLabel("Customer name").fill("Inbox test customer");
  await page.getByRole("textbox", { name: "Message" }).fill("Rice 1");
  await page.getByRole("button", { name: "Send test message" }).click();
  await expect(page.getByText("Message extraction ready")).toBeVisible();
  await page.getByRole("button", { name: "Review draft" }).click();
  await page
    .getByLabel("Customer", { exact: true })
    .selectOption({ label: "Perera Stores" });
  await page.getByLabel("I reviewed all extraction flags").check();
  await page.getByLabel("I have checked the customer").check();
  await page.getByRole("button", { name: "Confirm & create order" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Back to dashboard" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
});
