import type { Market } from "@/lib/api/schema";

export const PAGE_SIZE = 25;

export type MarketFilters = {
  view: "paired" | "all";
  /** Sent to the API; the backend filters by venue. */
  venue: Market["venue"] | "";
  /** Sent to the API before pagination. */
  status: Market["status"] | "";
  /** Sent to the API before pagination. */
  search: string;
  category: string;
  offset: number;
};

export const EMPTY_FILTERS: MarketFilters = {
  view: "paired",
  venue: "",
  status: "",
  search: "",
  category: "",
  offset: 0,
};

const VENUES: Market["venue"][] = ["kalshi", "polymarket", "polymarket_us"];
const STATUSES: Market["status"][] = ["open", "closed"];

/** Reads filters from the address bar, ignoring values the API does not accept. */
export function parseFilters(params: URLSearchParams): MarketFilters {
  const venue = params.get("venue") ?? "";
  const status = params.get("status") ?? "";
  const offset = Number.parseInt(params.get("offset") ?? "", 10);
  return {
    view: params.get("view") === "all" ? "all" : "paired",
    venue: VENUES.includes(venue as Market["venue"])
      ? (venue as Market["venue"])
      : "",
    status: STATUSES.includes(status as Market["status"])
      ? (status as Market["status"])
      : "",
    search: params.get("q") ?? "",
    category: params.get("category") ?? "",
    offset: Number.isFinite(offset) && offset > 0 ? offset : 0,
  };
}

/** Writes filters back to the address bar so a view can be shared or reloaded. */
export function serializeFilters(filters: MarketFilters) {
  const params = new URLSearchParams();
  if (filters.view === "all") params.set("view", "all");
  if (filters.venue) params.set("venue", filters.venue);
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("q", filters.search);
  if (filters.category) params.set("category", filters.category);
  if (filters.offset > 0) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `?${query}` : "";
}

/**
 * Local helper for recorded fixtures. Production browsing filters at the API.
 */
export function applyLocalFilters(markets: Market[], filters: MarketFilters) {
  const needle = filters.search.trim().toLowerCase();
  return markets.filter((market) => {
    if (filters.status && market.status !== filters.status) return false;
    if (!needle) return true;
    return (
      market.title.toLowerCase().includes(needle) ||
      market.external_id.toLowerCase().includes(needle)
    );
  });
}
