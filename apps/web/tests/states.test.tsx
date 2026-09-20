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
it("clearly identifies the preview without fabricated opportunities", () => {
  render(<Home />);
  expect(screen.getByText("No market data")).toBeVisible();
  expect(screen.getByText(/No live quotes/)).toBeVisible();
  expect(
    screen.getByRole("link", { name: /Check API connection/ }),
  ).toHaveAttribute("href", "/connection");
});
