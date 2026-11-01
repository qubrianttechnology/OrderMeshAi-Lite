import { test, expect } from "@playwright/test";

test("profile photo basics and full layout persist", async ({ page }) => {
  const r = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Settings Owner",
      organization_name: "Settings Studio",
      email: `settings-${Date.now()}@example.com`,
      password: "Settings-test-only-123",
    },
  });
  expect(r.status()).toBe(201);
  const org = (await r.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  expect(
    (
      await page.request.put("/api/business-profile", {
        headers,
        data: {
          business_type: "software",
          description: "Software studio building business applications",
          offerings: "Software projects",
          customers: "Local businesses",
          workflow: "Review project requirements first",
          hours: "Weekdays",
          payments: "Bank transfer",
          delivery: "Online delivery",
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto("/dashboard#Settings");
  const account = page.getByRole("region", {
    name: "Profile and basic settings",
  });
  await account.getByLabel("Full name", { exact: true }).fill("Updated Owner");
  await account
    .getByRole("button", { name: "Save profile", exact: true })
    .click();
  await expect(account.getByRole("status")).toHaveText("Profile saved.");
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=",
    "base64",
  );
  await account
    .getByLabel("Profile photo", { exact: true })
    .setInputFiles({ name: "avatar.png", mimeType: "image/png", buffer: png });
  await expect(
    account.getByRole("img", { name: "Your profile photo" }),
  ).toBeVisible();
  await account
    .getByLabel("Business name", { exact: true })
    .fill("Updated Studio");
  await account
    .getByRole("button", { name: "Save business basics", exact: true })
    .click();
  await expect(account.getByRole("status")).toHaveText(
    "Business basics saved.",
  );
  await page.getByLabel("Layout", { exact: true }).selectOption("full");
  await page
    .getByRole("button", { name: "Save dashboard layout", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Open POS", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(account.getByLabel("Full name", { exact: true })).toHaveValue(
    "Updated Owner",
  );
  await expect(
    account.getByLabel("Business name", { exact: true }),
  ).toHaveValue("Updated Studio");
  await expect(
    account.getByRole("img", { name: "Your profile photo" }),
  ).toBeVisible();
  expect(
    (
      await (
        await page.request.get("/api/business-profile", { headers })
      ).json()
    ).business_type,
  ).toBe("software");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Gross profit", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await account
    .getByRole("button", { name: "Remove photo", exact: true })
    .click();
  await expect(
    account.getByRole("img", { name: "Your profile photo" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Use business recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Open POS", exact: true }),
  ).toHaveCount(0);
});

test("inbox pin archive and unread actions persist", async ({ page }) => {
  const r = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Inbox Owner",
      organization_name: "Inbox Management",
      email: `manage-${Date.now()}@example.com`,
      password: "Inbox-test-only-123",
    },
  });
  expect(r.status()).toBe(201);
  const org = (await r.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  expect(
    (
      await page.request.post("/api/inbox/phone-numbers", {
        headers,
        data: {
          phone_number_id: "823456789012345",
          display_phone_number: "+94770001122",
        },
      })
    ).status(),
  ).toBe(201);
  expect(
    (
      await page.request.post("/api/inbox/simulator", {
        headers,
        data: {
          phone_number_id: "823456789012345",
          customer_phone: "+94770000222",
          customer_name: "Managed customer",
          text: "Synthetic stock question",
        },
      })
    ).status(),
  ).toBe(201);
  await page.goto("/dashboard/inbox");
  const list = page.getByRole("region", { name: "Conversations", exact: true });
  await page.getByRole("button", { name: "Pin chat", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Unpin chat", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Archive chat", exact: true }).click();
  await expect(list.locator("button.inbox-conversation")).toHaveCount(0);
  await page.getByLabel("Chat view", { exact: true }).selectOption("archived");
  await list.locator("button.inbox-conversation").click();
  await page
    .getByRole("button", { name: "Unarchive chat", exact: true })
    .click();
  await page.getByLabel("Chat view", { exact: true }).selectOption("active");
  await list.locator("button.inbox-conversation").click();
  await page.getByRole("button", { name: "Mark unread", exact: true }).click();
  await page.getByLabel("Chat view", { exact: true }).selectOption("unread");
  await expect(list.locator("button.inbox-conversation")).toHaveCount(1);
  await page.reload();
  await page.getByLabel("Chat view", { exact: true }).selectOption("all");
  await expect(list.locator("button.inbox-conversation")).toHaveCount(1);
});
