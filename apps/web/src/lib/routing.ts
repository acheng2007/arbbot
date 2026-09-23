/**
 * Decodes a dynamic route segment. Next hands these back percent-encoded, and
 * identifiers here contain characters like ":" that must be restored before the
 * value is used as an API parameter. A malformed sequence is passed through
 * unchanged so the API can report a clean "not found" instead of throwing.
 */
export function routeParam(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
