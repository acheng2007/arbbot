import type { ApiOperations, OperationId } from "./schema";

type Operation<K extends OperationId> = ApiOperations[K];

export type RequestArgs<K extends OperationId> = {
  params?: Operation<K>["params"];
  query?: Operation<K>["query"];
};

/** Substitutes `{name}` path parameters and appends defined query values. */
export function buildPath<K extends OperationId>(
  route: Operation<K>["route"],
  { params, query }: RequestArgs<K> = {},
): string {
  const path = (route as string).replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = (params as Record<string, string> | undefined)?.[name];
    if (value === undefined || value === "")
      throw new Error(`Missing path parameter "${name}" for ${route}`);
    return encodeURIComponent(value);
  });

  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(
    (query ?? {}) as Record<string, unknown>,
  )) {
    if (value === undefined || value === null || value === "") continue;
    search.set(name, String(value));
  }

  const suffix = search.toString();
  return suffix ? `${path}?${suffix}` : path;
}
