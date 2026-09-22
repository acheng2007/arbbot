/**
 * Where the data on screen came from. This is separate from the backend's own
 * simulation/live mode: a backend running in simulation still reports origin
 * "backend", while "fixtures" means no backend or exchange was involved at all.
 */
export type DataOrigin = "backend" | "fixtures";

export const ORIGIN_HEADER = "x-arbbot-origin";

export function parseOrigin(value: string | null): DataOrigin {
  return value === "fixtures" ? "fixtures" : "backend";
}
