import { test, expect } from "@playwright/test";

test("wholesale workspace manages vehicle parts and filters product categories", async ({
  page,
}) => {
  const registered = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Wholesale owner",
      organization_name: "Parts Distributors",
      email: `parts-${Date.now()}@example.com`,
      password: "Wholesale-test-password-123",
    },
  });
  expect(registered.status()).toBe(201);
  const org = (await registered.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const profile = await page.request.put("/api/business-profile", {
    headers,
    data: {
      business_type: "wholesale",
      primary_category: "vehicle_parts",
      description:
        "Wholesale vehicle parts distributor serving trade customers.",
      offerings: "Brake pads and filters by SKU and part number",
      customers: "Retail shops and garages",
      workflow:
        "Review request and confirm stock, quantities and price before dispatch.",
      hours: "Weekdays by appointment",
      payments: "Confirm payment terms manually",
      delivery: "Confirm delivery area manually",
    },
  });
  expect(profile.status()).toBe(200);
  const other = await page.request.post("/api/products", {
    headers,
    data: {
      sku: "USB-001",
      name: "USB cable",
      category: "electronics",
      price_minor: 50000,
    },
  });
  expect(other.status()).toBe(201);
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: "Products & inventory", exact: true })
    .click();
  await page.getByRole("button", { name: "Add product", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Product name", { exact: true })
    .fill("Brake pad set");
  await dialog.getByLabel("SKU", { exact: true }).fill("PAD-001");
  await dialog
    .getByLabel("Product category", { exact: true })
    .selectOption("vehicle_parts");
  await dialog.getByLabel("Unit price (LKR)").fill("5000");
  await dialog.getByLabel("Unit", { exact: true }).fill("sets");
  await dialog.getByLabel("Product aliases / part numbers").fill("OEM-04465");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).not.toBeVisible();
  const filter = page.getByLabel("Filter product category", { exact: true });
  await filter.selectOption("vehicle_parts");
  await expect(
    page.getByRole("cell", { name: "Vehicle parts", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "USB cable", exact: true }),
  ).not.toBeVisible();
  await page.getByLabel("Search inventory").fill("OEM-04465");
  await expect(
    page.getByRole("cell", { name: "PAD-001", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/wholesale-vehicle-parts.png",
    fullPage: true,
  });
  await filter.selectOption("electronics");
  await expect(page.getByText("No matching products")).toBeVisible();
  await page.getByLabel("Search inventory").fill("");
  await expect(
    page.getByRole("cell", { name: "USB-001", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Business Intelligence", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Show all questions", exact: true })
    .click();
  await expect(page.getByLabel("Primary product category")).toHaveValue(
    "vehicle_parts",
  );
  await page.getByLabel("Primary product category").selectOption("hardware");
  await page
    .getByRole("button", { name: "Save business profile", exact: true })
    .click();
  await expect(
    page.getByText("Business profile saved.", { exact: false }),
  ).toBeVisible();
  const saved = await (
    await page.request.get("/api/business-profile", { headers })
  ).json();
  expect(saved.profile.primary_category).toBe("hardware");
});
