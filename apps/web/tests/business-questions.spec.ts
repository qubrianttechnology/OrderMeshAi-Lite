import { test, expect } from "@playwright/test";

test("business intelligence collects dashboard answers without a document", async ({
  page,
}) => {
  const registered = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Question owner",
      organization_name: "Dashboard Parts Wholesale",
      email: `questions-${Date.now()}@example.com`,
      password: "Question-test-password-123",
    },
  });
  expect(registered.status()).toBe(201);
  const org = (await registered.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const documentRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/business-profile/document"))
      documentRequests.push(request.url());
  });
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: "Business Intelligence", exact: true })
    .click();
  const questions = page.getByRole("form", { name: "Business questions" });
  await expect(
    questions.getByRole("heading", { name: "Tell us about your business" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Download document template" }),
  ).not.toBeVisible();
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await expect(questions.getByRole("alert")).toContainText(
    "at least 20 characters",
  );
  await questions.getByRole("button", { name: /Review & save/ }).click();
  await questions
    .getByRole("button", { name: "Save business profile", exact: true })
    .click();
  await expect(
    questions.getByRole("heading", { name: "Tell us about your business" }),
  ).toBeVisible();
  await questions
    .getByRole("combobox", { name: "Business type", exact: true })
    .selectOption("wholesale");
  await questions
    .getByLabel("Primary product category")
    .selectOption("vehicle_parts");
  await questions
    .getByLabel("What does your business do?")
    .fill("We supply vehicle parts wholesale to garages and retail shops.");
  await questions
    .getByLabel("Products or services, aliases and pricing")
    .fill("Brake pads, filters and OEM part numbers, sold per set or carton.");
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await questions
    .getByLabel("Who are your customers?")
    .fill("Garages, spare-parts shops and regional distributors.");
  await questions
    .getByLabel("Workflow: inquiry to delivery and payment")
    .fill(
      "Check exact SKU and unit, review availability, owner approval, payment and dispatch.",
    );
  await questions
    .getByLabel("Details your team needs before confirming work")
    .fill("Part number, quantity, selling unit and delivery location.");
  await questions.getByRole("button", { name: "Back", exact: true }).click();
  await expect(questions.getByLabel("What does your business do?")).toHaveValue(
    "We supply vehicle parts wholesale to garages and retail shops.",
  );
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await expect(questions.getByLabel("Who are your customers?")).toHaveValue(
    "Garages, spare-parts shops and regional distributors.",
  );
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await questions
    .getByLabel("Payments, deposits, refunds and cancellation")
    .fill(
      "Bank transfer; credit and cancellation requests need owner approval.",
    );
  await questions
    .getByLabel("Delivery areas or project delivery process")
    .fill("Collect at our store or arrange delivery after approval.");
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await questions
    .getByLabel("Opening hours and response times")
    .fill("Monday to Saturday, 9am to 5pm.");
  await questions
    .getByLabel("Topics that always need human review")
    .fill("compatibility, credit request");
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await questions
    .getByLabel("Private message examples (one per line)")
    .fill("Bring the family album tonight");
  await questions.getByRole("button", { name: "Next", exact: true }).click();
  await expect(
    questions.getByRole("heading", { name: "Review your answers" }),
  ).toBeVisible();
  await expect(questions).toContainText("Vehicle parts");
  await questions
    .getByRole("button", { name: "Save business profile", exact: true })
    .click();
  await expect(
    page.getByText("Business profile saved.", { exact: false }),
  ).toBeVisible();
  const saved = await (
    await page.request.get("/api/business-profile", { headers })
  ).json();
  expect(saved.ready).toBe(true);
  expect(saved.profile.primary_category).toBe("vehicle_parts");
  expect(saved.profile.personal_examples).toBe(
    "Bring the family album tonight",
  );
  expect(saved.profile.document_name).toBeUndefined();
  expect(documentRequests).toEqual([]);
  await page.reload();
  await page
    .getByRole("button", { name: "Business Intelligence", exact: true })
    .click();
  await expect(page.getByLabel("What does your business do?")).toHaveValue(
    saved.profile.description,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/business-questions-mobile.png",
    fullPage: true,
  });
});
