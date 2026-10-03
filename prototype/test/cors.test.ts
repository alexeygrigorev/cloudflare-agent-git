import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { corsPolicyFromEnv, matchOrigin } from "../src/cors.js";

const ALLOWED = "https://dashboard.example";
const ALLOWED_TOO = "https://preview.example";
const DENIED = "https://evil.example";

describe("CORS preflight (PLAN-L1-REAL §5.7)", () => {
  it("answers OPTIONS for an allowlisted origin with the matched origin only", async () => {
    const res = await SELF.fetch("http://localhost/status", {
      method: "OPTIONS",
      headers: { origin: ALLOWED, "access-control-request-method": "POST" },
    });
    expect(res.status).toBe(204);
    expect(res.headers.get("access-control-allow-origin")).toBe(ALLOWED);
    expect(res.headers.get("access-control-allow-methods")).toBe("GET, POST");
    expect(res.headers.get("access-control-allow-headers")).toBe("Authorization, Content-Type");
    // §5.7: auth is header-based, never cookies — credentials stay OFF.
    expect(res.headers.get("access-control-allow-credentials")).toBe("false");
    expect(res.headers.get("access-control-max-age")).toBe("600");
    expect(res.headers.get("vary")).toBe("Origin");
  });

  it("a second allowlisted origin is echoed exactly (no wildcard collapse)", async () => {
    const res = await SELF.fetch("http://localhost/status", {
      method: "OPTIONS",
      headers: { origin: ALLOWED_TOO, "access-control-request-method": "GET" },
    });
    expect(res.status).toBe(204);
    expect(res.headers.get("access-control-allow-origin")).toBe(ALLOWED_TOO);
  });

  it("rejects preflight from a non-allowlisted origin without any CORS grant", async () => {
    const res = await SELF.fetch("http://localhost/status", {
      method: "OPTIONS",
      headers: { origin: DENIED, "access-control-request-method": "POST" },
    });
    expect(res.status).toBe(403);
    expect(res.headers.get("access-control-allow-origin")).toBeNull();
    expect(res.headers.get("access-control-allow-credentials")).toBeNull();
  });

  it("rejects preflight without an Origin header (browsers always send one)", async () => {
    const res = await SELF.fetch("http://localhost/status", {
      method: "OPTIONS",
      headers: { "access-control-request-method": "POST" },
    });
    expect(res.status).toBe(403);
    expect(res.headers.get("access-control-allow-origin")).toBeNull();
  });

  it("real responses carry the grant only for allowlisted origins; others are never reflected", async () => {
    const allowed = await SELF.fetch("http://localhost/status", { headers: { origin: ALLOWED } });
    expect(allowed.status).toBe(200);
    expect(allowed.headers.get("access-control-allow-origin")).toBe(ALLOWED);
    expect(allowed.headers.get("vary")).toBe("Origin");

    const denied = await SELF.fetch("http://localhost/status", { headers: { origin: DENIED } });
    expect(denied.status).toBe(200); // served, but the browser will block reading it
    expect(denied.headers.get("access-control-allow-origin")).toBeNull();

    const noOrigin = await SELF.fetch("http://localhost/status");
    expect(noOrigin.status).toBe(200);
    expect(noOrigin.headers.get("access-control-allow-origin")).toBeNull();
  });
});

describe("CORS policy derivation (unit)", () => {
  it("empty/unset ALLOWED_ORIGINS fails closed: no browser origin is allowed", () => {
    expect(corsPolicyFromEnv(undefined).allowedOrigins).toEqual([]);
    expect(corsPolicyFromEnv("").allowedOrigins).toEqual([]);
    expect(corsPolicyFromEnv(" , ").allowedOrigins).toEqual([]);
  });

  it("splits a comma-separated list and trims whitespace", () => {
    expect(corsPolicyFromEnv("https://a.example, https://b.example").allowedOrigins).toEqual([
      "https://a.example",
      "https://b.example",
    ]);
  });

  it("matching is exact — no wildcard or suffix match", () => {
    const policy = corsPolicyFromEnv("https://dashboard.example");
    expect(matchOrigin(policy, "https://dashboard.example")).toBe("https://dashboard.example");
    expect(matchOrigin(policy, "https://dashboard.example.evil.com")).toBeNull();
    expect(matchOrigin(policy, "https://dashboard.example:8443")).toBeNull();
    expect(matchOrigin(policy, "http://dashboard.example")).toBeNull();
    expect(matchOrigin(policy, null)).toBeNull();
  });
});
