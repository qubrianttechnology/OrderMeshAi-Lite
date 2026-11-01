import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { mkdirSync } from "node:fs";
const root = path.resolve(__dirname, "../..");
mkdirSync(path.join(root, ".e2e"), { recursive: true });
const python =
  process.env.PYTHON ||
  path.join(
    root,
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
process.env.ORDERMESH_E2E_DATABASE =
  process.env.ORDERMESH_E2E_DATABASE ||
  `sqlite:///${path.join(root, ".e2e", `browser-${Date.now()}.db`).replaceAll("\\", "/")}`;
process.env.ORDERMESH_E2E_PYTHON = python;
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90000,
  globalSetup: "./tests/global-setup.ts",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.E2E_BROWSER_CHANNEL || undefined,
      },
    },
  ],
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8100`,
      cwd: path.join(root, "services/api"),
      url: "http://127.0.0.1:8100/api/health",
      reuseExistingServer: false,
      env: {
        DATABASE_URL: process.env.ORDERMESH_E2E_DATABASE!,
        MIGRATION_DATABASE_URL: process.env.ORDERMESH_E2E_DATABASE!,
        APP_ENV: "development",
        APP_ORIGIN: "http://127.0.0.1:3100",
        ALLOW_REGISTRATION: "true",
        // Browser checks must never inherit real provider credentials from .env.
        AI_PROVIDER: "local",
        VOICE_TRANSCRIPTION_ENABLED: "false",
        IMAGE_EXTRACTION_ENABLED: "false",
        OPENAI_VISION_MODEL: "",
        OPENAI_TRANSCRIPTION_MODEL: "",
        OPENAI_API_KEY: "",
        OPENAI_MODEL: "",
        GOOGLE_OAUTH_CLIENT_ID: "",
        GOOGLE_OAUTH_CLIENT_SECRET: "",
        WHATSAPP_VERIFY_TOKEN: "",
        META_APP_SECRET: "",
        WHATSAPP_ACCESS_TOKEN: "",
        WHATSAPP_PHONE_NUMBER_ID: "",
        WHATSAPP_GRAPH_API_VERSION: "",
        WHATSAPP_ALLOWED_TEST_RECIPIENTS: "",
        WHATSAPP_TEST_MODE: "true",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: false,
      env: {
        API_BASE_URL: "http://127.0.0.1:8100",
        NEXT_TELEMETRY_DISABLED: "1",
        NEXT_DIST_DIR: ".next-e2e",
      },
      timeout: 120000,
    },
  ],
});
