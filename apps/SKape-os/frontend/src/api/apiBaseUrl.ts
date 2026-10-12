/**
 * Resolve the API base URL used by the Axios client.
 *
 * Production builds require an HTTPS URL whose path is `/api/v1`.
 * Development accepts that same shape, and also accepts HTTP when the
 * host is an explicit loopback address. Nothing falls back to localhost.
 * Error text does not include the supplied value.
 */

const API_PREFIX = "/api/v1";
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

export class ApiBaseUrlError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiBaseUrlError";
  }
}

export type ApiBaseUrlMode = "development" | "production";

function fail(message: string): never {
  throw new ApiBaseUrlError(message);
}

export function resolveApiBaseUrl(
  raw: string | undefined,
  mode: ApiBaseUrlMode,
): string {
  if (raw == null || raw.trim() === "") {
    fail("VITE_API_URL is required.");
  }

  let parsed: URL;
  try {
    parsed = new URL(raw.trim());
  } catch {
    fail("VITE_API_URL is not a valid URL.");
  }

  if (parsed.username !== "" || parsed.password !== "") {
    fail("VITE_API_URL must not include credentials.");
  }
  if (parsed.search !== "" || parsed.hash !== "") {
    fail("VITE_API_URL must not include a query or fragment.");
  }

  const path = parsed.pathname.replace(/\/+$/, "");
  if (path !== API_PREFIX) {
    fail("VITE_API_URL must end with /api/v1.");
  }

  const hostname = parsed.hostname.replaceAll(/^\[|\]$/g, "").toLowerCase();
  const loopback = LOOPBACK_HOSTS.has(hostname);
  if (mode === "production") {
    if (parsed.protocol !== "https:") {
      fail("VITE_API_URL must use HTTPS.");
    }
    if (loopback) {
      fail("VITE_API_URL must not use a local host.");
    }
  } else if (
    parsed.protocol !== "https:" &&
    !(parsed.protocol === "http:" && loopback)
  ) {
    fail(
      "VITE_API_URL must use HTTPS, or HTTP on localhost during development.",
    );
  }

  return `${parsed.protocol}//${parsed.host}${API_PREFIX}`;
}
