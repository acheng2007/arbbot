import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("persistent recorded classifications expose evidence without approval", async ({
  page,
}) => {
  const file = `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/classification-pair.json`;
  let match: { id: string };
  try {
    match = JSON.parse(readFileSync(file, "utf8"));
  } catch {
    test.skip(true, "Classification acceptance mode is not enabled");
    return;
  }
  await page.goto(`/matches/${match.id}`);
  await expect(
    page.getByRole("heading", { name: "AI suggests same event" }),
  ).toBeVisible();
  await expect(page.getByText("Candidate, not verified")).toBeVisible();
  await expect(page.getByText("No review recorded")).toBeVisible();
  await expect(
    page.getByText("Recorded model response, offline replay"),
  ).toBeVisible();
  const clause = page.getByText("cancellation: same meaning", { exact: true });
  await clause.click();
  await expect(
    page
      .getByRole("region", { name: "AI classification" })
      .locator("details")
      .filter({ has: clause })
      .locator("blockquote")
      .first(),
  ).toBeVisible();
  await expect(
    page.getByText(/Confidence is a model score, not measured accuracy/),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-classification.png`,
    fullPage: true,
  });
  await page
    .getByRole("region", { name: "AI classification" })
    .screenshot({
      path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-classification-panel.png`,
    });
  await page.goto("/matches");
  await page.getByLabel("AI classification filter").selectOption("suggested");
  await expect(
    page.getByRole("link", { name: /AI suggests same event/ }).first(),
  ).toBeVisible();
});
