import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  ApiBaseUrlError,
  resolveApiBaseUrl,
} from "../src/api/apiBaseUrl.ts";

const STAGING = "https://staging.example.invalid/api/v1";

function rejects(
  raw: string | undefined,
  mode: "development" | "production",
  message: string,
): void {
  assert.throws(
    () => resolveApiBaseUrl(raw, mode),
    (error: unknown) => {
      assert.ok(error instanceof ApiBaseUrlError);
      assert.equal(error.message, message);
      if (raw != null) {
        assert.equal(error.message.includes(raw), false);
      }
      return true;
    },
  );
}

describe("resolveApiBaseUrl", () => {
  it("accepts an HTTPS staging or production URL", () => {
    assert.equal(resolveApiBaseUrl(STAGING, "production"), STAGING);
    assert.equal(
      resolveApiBaseUrl(
        "https://api.example.invalid:8443/api/v1",
        "production",
      ),
      "https://api.example.invalid:8443/api/v1",
    );
  });

  it("drops a trailing slash without changing the Axios prefix", () => {
    assert.equal(
      resolveApiBaseUrl(`${STAGING}/`, "production"),
      STAGING,
    );
    assert.equal(
      resolveApiBaseUrl(`${STAGING}///`, "development"),
      STAGING,
    );
  });

  it("allows explicit loopback HTTP only in development", () => {
    assert.equal(
      resolveApiBaseUrl("http://localhost:8000/api/v1/", "development"),
      "http://localhost:8000/api/v1",
    );
    assert.equal(
      resolveApiBaseUrl("http://127.0.0.1:8000/api/v1", "development"),
      "http://127.0.0.1:8000/api/v1",
    );
    assert.equal(
      resolveApiBaseUrl("http://[::1]:8000/api/v1", "development"),
      "http://[::1]:8000/api/v1",
    );
  });

  it("rejects a missing, malformed, or non-HTTPS production URL", () => {
    rejects(undefined, "production", "VITE_API_URL is required.");
    rejects("   ", "production", "VITE_API_URL is required.");
    rejects("not a url", "production", "VITE_API_URL is not a valid URL.");
    rejects(
      "http://staging.example.invalid/api/v1",
      "production",
      "VITE_API_URL must use HTTPS.",
    );
  });

  it("rejects a local host in a production bundle", () => {
    rejects(
      "https://localhost/api/v1",
      "production",
      "VITE_API_URL must not use a local host.",
    );
    rejects(
      "https://127.0.0.1/api/v1",
      "production",
      "VITE_API_URL must not use a local host.",
    );
    rejects(
      "https://[::1]/api/v1",
      "production",
      "VITE_API_URL must not use a local host.",
    );
    rejects(
      "http://localhost:8000/api/v1",
      "production",
      "VITE_API_URL must use HTTPS.",
    );
  });

  it("rejects a path other than /api/v1", () => {
    rejects(
      "https://staging.example.invalid",
      "production",
      "VITE_API_URL must end with /api/v1.",
    );
    rejects(
      "https://staging.example.invalid/api/v1/extra",
      "production",
      "VITE_API_URL must end with /api/v1.",
    );
    rejects(
      "https://staging.example.invalid/api",
      "development",
      "VITE_API_URL must end with /api/v1.",
    );
  });

  it("rejects credentials and does not repeat them", () => {
    const raw = "https://user:s3cret-token@staging.example.invalid/api/v1";
    rejects(raw, "production", "VITE_API_URL must not include credentials.");
  });

  it("rejects a query or fragment", () => {
    rejects(
      `${STAGING}?token=hidden`,
      "production",
      "VITE_API_URL must not include a query or fragment.",
    );
    rejects(
      `${STAGING}#fragment`,
      "development",
      "VITE_API_URL must not include a query or fragment.",
    );
  });

  it("rejects non-local HTTP outside development", () => {
    rejects(
      "http://staging.example.invalid/api/v1",
      "development",
      "VITE_API_URL must use HTTPS, or HTTP on localhost during development.",
    );
  });
});
