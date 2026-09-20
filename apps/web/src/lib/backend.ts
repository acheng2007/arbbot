// Server-only configuration: never expose deployment URLs or credentials to browser bundles.
export function backendUrl() {
  const url = new URL(process.env.BACKEND_URL || "http://localhost:8000");
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    throw new Error(
      "BACKEND_URL must be an HTTP(S) URL without credentials, query, or fragment",
    );
  return url.toString().replace(/\/$/, "");
}
