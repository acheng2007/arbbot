import { expect, test } from "@playwright/test";

test("a reader can reach the evidence behind a proposed pair", async ({
  page,
}) => {
  await page.goto("/matches");

  // Recorded data must never read as live exchange data.
  await expect(page.getByText(/Recorded fixture data/)).toBeVisible();

  const candidate = page.getByRole("link", {
    name: /US CPI year-over-year above 3\.0%/,
  });
  await expect(candidate).toContainText("Verified in review");
  await expect(candidate).not.toContainText("Title similarity");
  await candidate.click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "US CPI year-over-year above 3.0%",
  );
  await page.getByText("Settlement terms", { exact: true }).click();
  await page.getByText("Source documents", { exact: true }).click();
  await page.getByText("Review evidence", { exact: true }).click();
  await expect(page.getByText("Unresolved assumptions")).toBeVisible();
  await expect(page.getByText(/resolves 50\/50/).first()).toBeVisible();

  // The exact published wording has to be inspectable, not paraphrased.
  await expect(
    page
      .getByText(
        /Revisions published after the initial release are disregarded/,
      )
      .first(),
  ).toBeVisible();

  await expect(page.getByText("Recorded review")).toBeVisible();
  await expect(page.getByText("CPI at or below 3.0%").first()).toBeVisible();
});

test("a conflicting pair is never presented as the same event", async ({
  page,
}) => {
  await page.goto("/matches/match-fed-2026-11");

  await expect(page.getByText("Operator veto", { exact: true })).toBeVisible();
  await expect(page.getByText("Terms conflict")).toBeVisible();
  await expect(
    page.getByText(
      /Supported checks found an event or settlement contradiction/,
    ),
  ).toBeVisible();
  await page.getByText("Review evidence", { exact: true }).click();
  await expect(page.getByText(/Intermeeting cuts settle these/)).toBeVisible();
});

test("an unreviewed candidate says so instead of implying approval", async ({
  page,
}) => {
  await page.goto("/matches/match-payrolls-2026-10");

  await expect(page.getByText("Unverified match")).toBeVisible();
  await expect(page.getByText("Terms incomplete")).toBeVisible();
  await expect(page.getByText("No review recorded")).toBeVisible();
  await expect(page.getByText(/Human review is optional/)).toBeVisible();
});

test("an unknown pair identifier gives a usable empty state", async ({
  page,
}) => {
  await page.goto("/matches/does-not-exist");
  await expect(page.getByText("This pair is not available")).toBeVisible();
});
