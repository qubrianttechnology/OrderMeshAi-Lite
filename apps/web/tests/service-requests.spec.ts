import { test, expect } from "@playwright/test";

test("extract, edit and complete a service request without creating an order", async ({
  page,
}) => {
  await page.goto("/sign-up");
  await page.getByLabel("Your name", { exact: true }).fill("Service Owner");
  await page.getByLabel("Business name").fill("Service Workflow Test");
  await page
    .getByLabel("Email address")
    .fill(`service-${Date.now()}@example.com`);
  await page.getByLabel(/^Password/).fill("Service-test-password-123");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Business at a glance" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Service and project requests" })
    .check();
  await page
    .getByRole("button", { name: "Save dashboard layout", exact: true })
    .click();
  await expect(
    page.getByText("Dashboard layout saved for this business."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Service requests", exact: true })
    .click();
  await page
    .getByLabel("Customer service message")
    .fill(
      "We need a website with online booking; Budget: LKR 150,000; Deadline: 30 November; Meeting: Friday 2pm; Email: client@example.com",
    );
  await page
    .getByRole("button", { name: "Extract service request", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review service request", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Budget", { exact: true })).toHaveValue(
    "Budget: LKR 150,000",
  );
  await expect(page.getByLabel("Deadline", { exact: true })).toHaveValue(
    "Deadline: 30 November",
  );
  await expect(page.getByLabel("Appointment", { exact: true })).toHaveValue(
    "Meeting: Friday 2pm",
  );
  await expect(
    page.getByRole("button", { name: "Accept request", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Budget", { exact: true })
    .fill("Agreed budget: LKR 140,000");
  await page
    .getByLabel("I reviewed the message, requirements, budget and dates.")
    .check();
  await page
    .getByRole("button", { name: "Accept request", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Mark completed", exact: true }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("button", { name: "Service requests", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Review request", exact: true })
    .click();
  await expect(page.getByLabel("Budget", { exact: true })).toHaveValue(
    "Agreed budget: LKR 140,000",
  );
  await page
    .getByLabel("I reviewed the message, requirements, budget and dates.")
    .check();
  await page
    .getByRole("button", { name: "Mark completed", exact: true })
    .click();
  await expect(page.getByLabel("Budget", { exact: true })).toBeDisabled();
  await page.screenshot({
    path: "test-results/service-request-reviewed.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Orders", exact: true }).click();
  await expect(
    page.getByText("Your next order starts here", { exact: true }),
  ).toBeVisible();
});
