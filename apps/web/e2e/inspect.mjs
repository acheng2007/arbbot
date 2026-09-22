// Development-only visual sweep. Run with `node e2e/inspect.mjs` while a dev
// server is serving fixtures; it is not part of the test suite.
import { chromium, devices } from "@playwright/test";

const base = process.env.INSPECT_URL ?? "http://127.0.0.1:3100";
const pages = [
  ["overview", "/"],
  ["opportunities", "/opportunities"],
  ["opportunity-detail", "/opportunities/opp-cpi-2026-09-01"],
  ["matches", "/matches"],
  ["match-verified", "/matches/match-cpi-2026-09"],
  ["match-rejected", "/matches/match-fed-2026-11"],
  ["match-incomplete", "/matches/match-payrolls-2026-10"],
  ["markets", "/markets"],
  ["market-detail", "/markets/kalshi%3ACPIYOY-26SEP-T3.0"],
  ["market-empty-book", "/markets/kalshi%3APAYROLLS-26OCT-T150"],
];

const browser = await chromium.launch();
for (const [name, viewport] of [
  ["desktop", { viewport: { width: 1440, height: 900 } }],
  ["mobile", devices["iPhone 13"]],
]) {
  const context = await browser.newContext({ ...viewport });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));

  for (const [label, path] of pages) {
    await page.goto(`${base}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    if (overflow > 0) problems.push(`${label}: horizontal overflow ${overflow}px`);
    await page.screenshot({
      path: `test-results/inspect-${name}-${label}.png`,
      fullPage: true,
    });
  }
  console.log(name, problems.length ? problems : "clean");
  await context.close();
}
await browser.close();
