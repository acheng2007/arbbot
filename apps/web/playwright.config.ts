import { defineConfig, devices } from "@playwright/test";
const baseURL = process.env.ARBBOT_E2E_BASE_URL ?? "http://127.0.0.1:3100";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer:
    process.env.ARBBOT_E2E_NO_SERVER === "true"
      ? undefined
      : {
          command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
          url: "http://127.0.0.1:3100",
          reuseExistingServer: !process.env.CI,
          // Browser tests run against the recorded fixture dataset so they never
          // depend on a backend, a database, or exchange connectivity.
          env: { ARBBOT_WEB_DATA_SOURCE: "fixtures" },
        },
});
