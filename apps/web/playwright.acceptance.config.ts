import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./acceptance",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 30000 },
  use: { baseURL: process.env.ARBBOT_ACCEPTANCE_WEB_URL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" } },
  ],
});
