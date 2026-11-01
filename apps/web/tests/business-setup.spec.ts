import { test, expect } from "@playwright/test";

test("restored green workspace supports an agency profile and services without stock", async ({
  page,
}) => {
  await page.goto("/sign-up");
  await page.getByLabel("Your name", { exact: true }).fill("Agency Owner");
  await page.getByLabel("Business name").fill("Green Agency");
  await page
    .getByLabel("Email address")
    .fill(`agency-${Date.now()}@example.com`);
  await page.getByLabel(/^Password/).fill("Agency-test-password-123");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Business at a glance" }),
  ).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveAttribute(
    "data-theme",
    "light",
  );
  await page.getByRole("button", { name: "Set up my business" }).click();
  await expect(
    page.getByRole("heading", { name: "Business profile", exact: true }),
  ).toBeVisible();
  await page
    .getByText("Already have a document? Import it here (optional)", {
      exact: true,
    })
    .click();
  await page.getByLabel("Business document", { exact: true }).setInputFiles({
    name: "agency.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Our agency designs websites for local shops. We quote, obtain approval and deliver a complete website.",
    ),
  });
  await expect(
    page.getByText(
      "Document saved. Review and complete your business answers.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Show all questions", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Business type", exact: true })
    .selectOption("agency");
  await page
    .getByLabel("What does your business do?")
    .fill("We design websites and manage marketing campaigns for local shops.");
  await page
    .getByLabel("Products or services, aliases and pricing")
    .fill("Website development, digital marketing and software maintenance");
  await page
    .getByLabel("Who are your customers?")
    .fill("Local shops and growing businesses");
  await page
    .getByLabel("Workflow: inquiry to delivery and payment")
    .fill(
      "Inquiry, scope, quotation, client approval, development, delivery and final payment.",
    );
  await page
    .getByLabel("Opening hours and response times")
    .fill("Monday to Friday 9am to 5pm");
  await page
    .getByLabel("Payments, deposits, refunds and cancellation")
    .fill("50% deposit by bank transfer and balance on completion");
  await page
    .getByLabel("Delivery areas or project delivery process")
    .fill("Remote project delivery at agreed milestones");
  await page.getByRole("button", { name: "Save business profile" }).click();
  await expect(
    page.getByText(
      "Business profile saved. Your dashboard and message routing now use this context.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Business profile", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Services", exact: true }).click();
  await page.getByRole("button", { name: "Add service", exact: true }).click();
  await page.getByLabel("Service name").fill("Website");
  await page.getByLabel("SKU", { exact: true }).fill("WEB-1");
  await page.getByLabel("Unit price (LKR)").fill("50000");
  await expect(
    page.getByRole("checkbox", { name: "Track inventory for this item" }),
  ).not.toBeChecked();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Website", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Adjust stock", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(
    page.getByText("Service offerings", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Service requests received", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Project requests", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Clients", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Orders", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Product or service catalog" })
    .uncheck();
  await page
    .getByRole("button", { name: "Save dashboard layout", exact: true })
    .click();
  await expect(
    page.getByText("Dashboard layout saved for this business."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Services", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Services", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: "Product or service catalog" }),
  ).not.toBeChecked();
  await page
    .getByRole("button", { name: "Use business recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Services", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: "test-results/restored-agency-dashboard.png",
    fullPage: true,
  });
});
