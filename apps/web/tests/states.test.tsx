import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { LoadingState, ErrorState, StaleNotice } from "@/components/states";
import Home from "@/app/page";
it("announces loading without exposing decorative icons", () => {
  render(<LoadingState label="Loading markets" />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading markets");
});
it("offers an operable retry action", async () => {
  const retry = vi.fn();
  render(<ErrorState onRetry={retry} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Unable to load");
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
});
it("announces stale evidence", () => {
  render(<StaleNotice>Quotes are stale</StaleNotice>);
  expect(screen.getByRole("status")).toHaveTextContent("Quotes are stale");
});
it("routes to each workspace area without fabricating figures", () => {
  render(<Home />);
  expect(
    screen.getByText(/Nothing on this site places an order/),
  ).toBeVisible();
  expect(screen.getByText(/Similar titles do not establish/)).toBeVisible();
  for (const [name, href] of [
    [/View opportunities/, "/opportunities"],
    [/Check API connection/, "/connection"],
    [/Inspect markets/, "/markets"],
    [/Compare contracts/, "/matches"],
  ] as const)
    expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
});
