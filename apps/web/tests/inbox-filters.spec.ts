import { test, expect } from "@playwright/test";

test("inbox filters chats and messages by category and searches older text", async ({
  page,
}) => {
  const registered = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Filter Reviewer",
      organization_name: "Filter Workspace",
      email: `filter-${Date.now()}@example.com`,
      password: "Filter-test-password-123",
    },
  });
  expect(registered.status()).toBe(201);
  const org = (await registered.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const connected = await page.request.post("/api/inbox/phone-numbers", {
    headers,
    data: {
      phone_number_id: "923456789012345",
      display_phone_number: "+94770001122",
    },
  });
  expect(connected.status()).toBe(201);
  const samples = [
    {
      phone: "+94770000101",
      name: "Private contact",
      text: "Keepsake-original birthday greeting",
      category: "personal",
    },
    {
      phone: "+94770000101",
      name: "Private contact",
      text: "Latest family greeting",
      category: "personal",
    },
    {
      phone: "+94770000102",
      name: "Spam contact",
      text: "Unwanted promotion",
      category: "spam",
    },
    {
      phone: "+94770000103",
      name: "Business contact",
      text: "Website consultation",
      category: "business_inquiry",
    },
  ];
  for (const sample of samples) {
    const simulated = await page.request.post("/api/inbox/simulator", {
      headers,
      data: {
        phone_number_id: "923456789012345",
        customer_phone: sample.phone,
        customer_name: sample.name,
        text: sample.text,
      },
    });
    expect(simulated.status()).toBe(201);
    const conversations = await (
      await page.request.get("/api/inbox/conversations", { headers })
    ).json();
    const conversation = conversations.find(
      (item: { customer_phone: string }) =>
        item.customer_phone.replaceAll("+", "") ===
        sample.phone.replaceAll("+", ""),
    );
    const messages = await (
      await page.request.get(
        `/api/inbox/conversations/${conversation.id}/messages`,
        { headers },
      )
    ).json();
    const message = messages.find(
      (item: { text: string }) => item.text === sample.text,
    );
    const changed = await page.request.put(
      `/api/inbox/messages/${message.id}/category`,
      { headers, data: { category: sample.category } },
    );
    expect(changed.status()).toBe(200);
  }
  await page.goto("/dashboard/inbox");
  const list = page.getByRole("region", { name: "Conversations", exact: true });
  const filter = page.getByLabel("Filter messages", { exact: true });
  await expect(list.locator("button.inbox-conversation")).toHaveCount(3);
  await filter.selectOption("personal");
  await expect(list.locator("button.inbox-conversation")).toHaveCount(1);
  await expect(
    list.getByText("Private contact", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search conversations").fill("Keepsake-original");
  await expect(list.locator("button.inbox-conversation")).toHaveCount(1);
  await page.getByLabel("Search conversations").fill("");
  await filter.selectOption("spam");
  await expect(list.getByText("Spam contact", { exact: true })).toBeVisible();
  await expect(list.locator("button.inbox-conversation")).toHaveCount(1);
  await expect(
    page
      .getByRole("region", { name: "Message thread" })
      .getByText("Unwanted promotion", { exact: true }),
  ).toBeVisible();
  await filter.selectOption("business");
  await expect(
    list.getByText("Business contact", { exact: true }),
  ).toBeVisible();
  await expect(list.locator("button.inbox-conversation")).toHaveCount(1);
  await filter.selectOption("needs_review");
  await expect(list.getByText("No matching conversations")).toBeVisible();
  await filter.selectOption("all");
  await expect(list.locator("button.inbox-conversation")).toHaveCount(3);
});
