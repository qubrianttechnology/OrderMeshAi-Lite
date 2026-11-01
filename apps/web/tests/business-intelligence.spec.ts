import { test, expect } from "@playwright/test";

test("business intelligence reads document suggestions, saves examples and previews private/spam safely", async ({
  page,
}) => {
  await page.goto("/sign-up");
  await page
    .getByLabel("Your name", { exact: true })
    .fill("Intelligence Owner");
  await page.getByLabel("Business name").fill("Context Agency");
  await page
    .getByLabel("Email address")
    .fill(`intelligence-${Date.now()}@example.com`);
  await page.getByLabel(/^Password/).fill("Business-intelligence-test-123");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Business Intelligence", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Test message filtering", exact: true }),
  ).toBeVisible();
  await page
    .getByText("Already have a document? Import it here (optional)", {
      exact: true,
    })
    .click();
  await page.getByLabel("Business document", { exact: true }).setInputFiles({
    name: "agency-context.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      [
        "Description: We build booking websites and software for local businesses.",
        "Offerings: Websites, hosting and maintenance",
        "Customers: Cafes, salons and local shops",
        "Workflow: Inquiry, scope, quote, approval and project delivery",
        "Hours: Monday to Friday 9 to 5",
        "Payments: Bank transfer and deposit before work",
        "Delivery: Remote delivery after milestone approval",
        "Required details: Scope, contact, budget and deadline",
        "Review triggers: legal dispute",
        "Business examples:",
        "Can you redesign our customer portal?",
        "Personal examples:",
        "Bring the family album tonight",
        "Spam examples:",
        "Unsolicited galaxy investment pitch",
      ].join("\n"),
    ),
  });
  await page
    .getByRole("button", { name: "Review document suggestions", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Show all questions", exact: true })
    .click();
  await expect(page.getByLabel("Who are your customers?")).toHaveValue(
    "Cafes, salons and local shops",
  );
  await page
    .getByRole("combobox", { name: "Business type", exact: true })
    .selectOption("agency");
  await page
    .getByRole("button", { name: "Save business profile", exact: true })
    .click();
  await expect(
    page.getByText(
      "Business profile saved. Your dashboard and message routing now use this context.",
    ),
  ).toBeVisible();
  for (const [text, category] of [
    ["Bring the family album tonight", "personal"],
    ["Unsolicited galaxy investment pitch", "spam"],
    ["Can you redesign our customer portal?", "business inquiry"],
    ["Please help with a legal dispute", "needs review"],
  ]) {
    await page.getByLabel("Sample WhatsApp message").fill(text);
    await page
      .getByRole("button", { name: "Preview classification", exact: true })
      .click();
    await expect(
      page
        .getByRole("status")
        .filter({ has: page.locator("strong", { hasText: category }) }),
    ).toBeVisible();
  }
  await page.reload();
  await page
    .getByRole("button", { name: "Business Intelligence", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Show all questions", exact: true })
    .click();
  await expect(
    page.getByLabel("Private message examples (one per line)"),
  ).toHaveValue("Bring the family album tonight");
  await expect(
    page.getByRole("button", { name: "Project requests", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/business-intelligence.png",
    fullPage: true,
  });
});
