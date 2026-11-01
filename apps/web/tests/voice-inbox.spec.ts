import { test, expect } from "@playwright/test";

test("voice inbox shows failure, retry and reviewable Tamil transcript", async ({
  page,
}) => {
  const register = await page.request.post("/api/auth/register", {
    headers: { "X-OrderMesh": "1" },
    data: {
      name: "Voice Reviewer",
      organization_name: "Voice Workspace",
      email: `voice-${Date.now()}@example.com`,
      password: "Voice-test-password-123",
    },
  });
  expect(register.status()).toBe(201);
  const org = (await register.json()).organization_id;
  const headers = { "X-OrderMesh": "1", "X-Organization-ID": org };
  const phone = await page.request.post("/api/inbox/phone-numbers", {
    headers,
    data: {
      phone_number_id: "912345678901234",
      display_phone_number: "+94770001122",
      business_account_id: "987654321",
    },
  });
  expect(phone.status()).toBe(201);
  const simulated = await page.request.post("/api/inbox/simulator", {
    headers,
    data: {
      phone_number_id: "912345678901234",
      customer_phone: "+94770002233",
      customer_name: "Voice Customer",
      text: "Hello",
    },
  });
  expect(simulated.status()).toBe(201);
  let transcribed = false;
  await page.route("**/api/inbox/conversations/*/messages", (route) =>
    route.fulfill({
      json: [
        {
          id: "voice-ui-test",
          direction: "inbound",
          message_type: "audio",
          text: transcribed ? "அரிசி 2" : null,
          transcription_status: transcribed ? "transcribed" : "failed",
          transcription_error: transcribed
            ? ""
            : "Speech transcription provider is unavailable",
          sent_at: new Date().toISOString(),
          extraction_draft_id: null,
          delivery_status: null,
          delivery_error_code: "",
          category: "needs_review",
          category_reason: "Review voice details",
          category_reviewed: false,
          is_simulated: true,
        },
      ],
    }),
  );
  await page.route(
    "**/api/inbox/messages/voice-ui-test/transcription/retry",
    (route) => {
      expect(route.request().method()).toBe("POST");
      transcribed = true;
      return route.fulfill({ json: { status: "queued" } });
    },
  );
  await page.goto("/dashboard/inbox");
  await expect(page.locator("article").getByRole("status")).toContainText(
    "Speech transcription provider is unavailable",
  );
  await page.getByRole("button", { name: "Retry transcription" }).click();
  await expect(page.getByText("அரிசி 2", { exact: true })).toBeVisible();
  await expect(page.getByText(/Voice transcript.*check names/)).toBeVisible();
  await page.screenshot({
    path: "test-results/voice-inbox-tamil.png",
    fullPage: true,
  });
  const orders = await page.request.get("/api/orders", { headers });
  expect(await orders.json()).toEqual([]);
});
