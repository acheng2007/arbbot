import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

test("connected discoveries, evidence, feeds and snapshot withdrawal", async ({
  page,
}) => {
  const output = process.env.ARBBOT_ACCEPTANCE_OUTPUT!;
  const pair = JSON.parse(
    readFileSync(`${output}/discovery-pair.json`, "utf8"),
  );
  await page.goto("/markets?category=politics&relationship=unverified");
  await expect(
    page.getByRole("heading", { name: "Discoveries", exact: true }),
  ).toBeVisible();
  const card = page
    .getByRole("article")
    .filter({
      has: page.getByRole("link", { name: /Democrats win the House/ }),
    })
    .first();
  await expect(card.getByText("Unverified match")).toBeVisible();
  await card.getByRole("link", { name: /Democrats win the House/ }).click();
  await expect(page).toHaveURL(new RegExp(`/matches/${pair.id}`));
  await expect(
    page.getByRole("heading", { name: "Automatic settlement assessment" }),
  ).toBeVisible();
  await page
    .getByText("AI classification and matching rationale", { exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "AI suggests same event" }),
  ).toBeVisible();
  await expect(page.getByText(/^Event finding:/)).toContainText(
    "confidence score 0.10",
  );
  await expect(page.getByText(/Outcome relationship: aligned/)).toBeVisible();
  await page.getByText("Matching assessment history", { exact: true }).click();
  await expect(
    page.getByText(/Recorded model findings explain past inputs/),
  ).toBeVisible();
  await page.screenshot({
    path: `${output}/${test.info().project.name}-political-assessment.png`,
    fullPage: true,
  });
  await page.goto("/opportunities?view=potential");
  await expect(
    page.getByText("Potential price gap", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/Ordinary-outcome price gaps/)).toBeVisible();
  await page
    .getByRole("link", { name: /US CPI|synthetic/i })
    .first()
    .click();
  if (
    await page
      .getByRole("button", { name: "Inspect historical result" })
      .isVisible()
  )
    await page
      .getByRole("button", { name: "Inspect historical result" })
      .click();
  await expect(page.getByText(/Acquisition cost:/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `${output}/${test.info().project.name}-potential-details.png`,
    fullPage: true,
  });
  await page.goto("/opportunities?view=qualified");
  await expect(page.getByText("Estimated net profit")).toBeVisible();
  const file = process.env.ARBBOT_ACCEPTANCE_CONTROL!;
  const change = (values: Record<string, unknown>) => {
    const state = JSON.parse(readFileSync(file, "utf8"));
    writeFileSync(
      file,
      JSON.stringify({ ...state, ...values, epoch: state.epoch + 1 }),
    );
  };
  try {
    change({ fee_failure: true });
    await expect(page.getByText("No opportunities right now")).toBeVisible({
      timeout: 45000,
    });
    await expect(page).toHaveURL(/view=qualified/);
    await page.screenshot({
      path: `${output}/${test.info().project.name}-fee-withdrawal.png`,
      fullPage: true,
    });
  } finally {
    change({ fee_failure: false });
  }
  await expect(page.getByText("Estimated net profit")).toBeVisible({
    timeout: 45000,
  });
});
