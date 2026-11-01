import { test, expect } from "@playwright/test";

test("order image is uploaded for review without creating an order", async ({
  page,
}) => {
  const headers = { "X-OrderMesh": "1" };
  const registered = await page.request.post("/api/auth/register", {
    headers,
    data: {
      name: "Image Reviewer",
      organization_name: "Image Workspace",
      email: `image-${Date.now()}@example.com`,
      password: "Image-test-password-123",
    },
  });
  expect(registered.status()).toBe(201);
  const org = (await registered.json()).organization_id;
  const tenantHeaders = { ...headers, "X-Organization-ID": org };
  await page.route("**/api/integrations", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.images = { status: "configured" };
    await route.fulfill({ json: data });
  });
  await page.route("**/api/extractions/image", (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["content-type"]).toBe("image/png");
    expect(route.request().postDataBuffer()!.length).toBeGreaterThan(0);
    return route.fulfill({
      status: 201,
      json: {
        id: "image-draft",
        source_text: "Rice 2",
        result: {
          provider: "local-rules-v1",
          language: "en",
          source_type: "image_text",
          flags: ["image_text_requires_review"],
          delivery_instructions: null,
          requires_confirmation: true,
          items: [
            {
              source: "Rice 2",
              product_id: null,
              product_name: null,
              quantity: 2,
              unit: null,
              confidence: 0.2,
              flags: ["unknown_product"],
            },
          ],
        },
      },
    });
  });
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: "Order assistant", exact: true })
    .click();
  await page.getByLabel("Order image", { exact: true }).setInputFiles({
    name: "order.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await expect(page.getByAltText("Selected order image")).toBeVisible();
  await page
    .getByRole("button", { name: "Read order image", exact: true })
    .click();
  await expect(
    page.getByText("Text read from image - verify against your original", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("Rice 2", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review & confirm", exact: true }),
  ).toBeVisible();
  expect(
    await (
      await page.request.get("/api/orders", { headers: tenantHeaders })
    ).json(),
  ).toEqual([]);
});
