import { expect, test } from "@playwright/test";
test("responsive navigation and keyboard skip link", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Markets");
  await page.screenshot({
    path: `test-results/overview-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.route("**/api/connection", (route) =>
    route.fulfill({ json: { status: "ok", mode: "simulation" } }),
  );
  await page.getByRole("link", { name: "Connection status" }).click();
  await expect(page.getByRole("status")).toHaveText("Backend reachable");
  await expect(page.getByText("Simulation", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/connection$/);
  await page.route("**/api/connection", (route) =>
    route.fulfill({ status: 503, json: { error: "Unavailable" } }),
  );
  await page.getByRole("button", { name: "Check again" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Backend unavailable",
  );
  await expect(
    page.getByText(/previous connection result is out of date/),
  ).toBeVisible();
});
