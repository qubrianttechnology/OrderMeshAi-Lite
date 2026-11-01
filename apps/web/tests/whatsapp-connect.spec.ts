import { test, expect } from "@playwright/test";

for (const needsPin of [false, true])
  test(`number-first connection opens inbox (registration PIN: ${needsPin})`, async ({
    page,
  }) => {
    const popupUrls: string[] = [];
    await page.addInitScript(() => {
      const original = window.open;
      window.open = function (url, target, features) {
        (window as unknown as { testPopupUrls: string[] }).testPopupUrls ??= [];
        (window as unknown as { testPopupUrls: string[] }).testPopupUrls.push(
          String(url),
        );
        return original.call(window, url, target, features);
      };
    });
    const sdkRedirect =
      "https://staticxx.facebook.com/x/connect/xd_arbiter/?version=46#cb=browser-test&domain=127.0.0.1";
    await page.context().route("https://www.facebook.com/**", (route) => {
      const nested =
        needsPin && !route.request().url().includes("/completion-frame");
      return route.fulfill({
        status: 200,
        contentType: "text/html",
        body: nested
          ? '<iframe src="https://www.facebook.com/completion-frame"></iframe>'
          : `<script>(window.top.opener).postMessage({type:"WA_EMBEDDED_SIGNUP",event:"FINISH",data:{waba_id:"987654321"}},"http://127.0.0.1:3100")</script>`,
      });
    });
    const config = {
      configured: true,
      missing: [],
      app_id: "test-app",
      config_id: "test-config",
      graph_version: "v26.0",
      origin: "http://127.0.0.1:3100",
      callback_url: "https://test.example/webhooks/whatsapp",
    };
    await page.route("**/api/inbox/meta-signup/status", (route) =>
      route.fulfill({ json: config }),
    );
    await page.route("**/api/inbox/meta-signup/begin", (route) => {
      expect(route.request().postDataJSON()).toEqual({
        phone_number: "+94770001122",
      });
      return route.fulfill({
        status: 201,
        json: { ...config, attempt_id: "test-attempt" },
      });
    });
    await page.route("https://connect.facebook.net/en_US/sdk.js", (route) =>
      route.fulfill({
        contentType: "application/javascript",
        body: `window.FB={init:function(){},login:function(callback,options){if(callback.constructor.name!=='Function')throw new Error('SDK requires a normal callback');if(options.response_type!=='code')throw new Error('Expected code flow');window.open('https://www.facebook.com/v26.0/dialog/oauth?client_id=test-app&redirect_uri='+encodeURIComponent('${sdkRedirect}'));callback({authResponse:{code:'synthetic-one-use-code'}})}};`,
      }),
    );
    await page.route("**/api/inbox/meta-signup/exchange", async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        attempt_id: "test-attempt",
        code: "synthetic-one-use-code",
        redirect_uri: sdkRedirect,
        business_account_id: "987654321",
      });
      await route.fulfill({
        json: {
          choices: [
            {
              phone_number_id: "123456789",
              display_phone_number: "+94770001122",
              verified_name: "Test Client",
            },
          ],
        },
      });
    });
    let confirmed = false;
    let confirmCalls = 0;
    await page.route("**/api/inbox/meta-signup/confirm", async (route) => {
      confirmCalls++;
      expect(route.request().postDataJSON()).toEqual({
        attempt_id: "test-attempt",
        phone_number_id: "123456789",
        human_confirmed: true,
        pin: needsPin && confirmCalls > 1 ? "123456" : null,
      });
      if (needsPin && confirmCalls === 1) {
        await route.fulfill({
          status: 422,
          json: {
            detail:
              "Enter a six-digit registration PIN for this Cloud API number",
          },
        });
        return;
      }
      confirmed = true;
      await route.fulfill({
        json: { connected: true, display_phone_number: "+94770001122" },
      });
    });
    await page.goto("/sign-up");
    await page.getByLabel("Your name", { exact: true }).fill("Meta Owner");
    await page.getByLabel("Business name").fill("Meta Connect Test");
    await page
      .getByLabel("Email address")
      .fill(`meta-${Date.now()}@example.com`);
    await page.getByLabel(/^Password/).fill("Meta-test-password-123");
    await page
      .getByRole("button", { name: "Create workspace", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Business at a glance" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Set up my business", exact: true })
      .click();
    await page.getByLabel("WhatsApp business number").fill("+94770001122");
    await page
      .getByRole("button", { name: "Connect WhatsApp", exact: true })
      .click();
    if (needsPin) {
      await expect(
        page
          .getByRole("region", { name: "WhatsApp connection" })
          .getByRole("alert"),
      ).toContainText("six-digit registration PIN");
      expect(confirmed).toBe(false);
      await page
        .getByLabel("Six-digit Cloud API registration PIN")
        .fill("123456");
      await page
        .getByRole("button", { name: "Connect selected number", exact: true })
        .click();
    }
    await expect(page).toHaveURL(/\/dashboard\/inbox/);
    expect(confirmed).toBe(true);
    popupUrls.push(
      ...(await page.evaluate(
        () =>
          (window as unknown as { testPopupUrls: string[] }).testPopupUrls ||
          [],
      )),
    );
    expect(popupUrls).toEqual(["about:blank"]);
  });
