import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { parseRateLimit } from "../src/index.js";
import { ADMIN_TOKEN, RUNNER_TOKEN } from "./helpers.js";

// RATE_LIMIT_PER_MINUTE is unset in the test bindings, so the default (120)
// applies; parseRateLimit(undefined) is the authoritative in-test value.
const LIMIT = parseRateLimit(undefined);

async function getStatus(token?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (token) {
    headers.authorization = `Bearer ${token}`;
  }
  return SELF.fetch("http://localhost/status", { headers });
}

describe("per-principal rate limiting (PLAN-L1-REAL §5.4)", () => {
  it(`429s after ${LIMIT} requests/minute with Retry-After, never echoing the token`, async () => {
    let saw429: Response | null = null;
    for (let i = 0; i < LIMIT + 10; i++) {
      const res = await getStatus(ADMIN_TOKEN);
      if (res.status === 429) {
        saw429 = res;
        break;
      }
      expect(res.status, `request ${i + 1}`).toBe(200);
    }
    expect(saw429).not.toBeNull();
    const retryAfter = Number(saw429!.headers.get("retry-after"));
    expect(retryAfter).toBeGreaterThan(0);
    expect(retryAfter).toBeLessThanOrEqual(60);
    const body = await saw429!.text();
    expect(body).toContain("rate limit exceeded");
    expect(body).not.toContain(ADMIN_TOKEN);
  });

  it("limits are per principal: another token and anonymous callers keep working", async () => {
    for (let i = 0; i < LIMIT + 5; i++) {
      await getStatus(ADMIN_TOKEN);
    }
    const runner = await getStatus(RUNNER_TOKEN);
    expect(runner.status).toBe(200);
    const anon = await getStatus();
    expect(anon.status).toBe(200);
  });

  it("CORS preflight stays exempt even for a rate-limited origin", async () => {
    for (let i = 0; i < LIMIT + 5; i++) {
      await getStatus(ADMIN_TOKEN);
    }
    const pre = await SELF.fetch("http://localhost/status", {
      method: "OPTIONS",
      headers: { origin: "https://dashboard.example", "access-control-request-method": "POST" },
    });
    expect(pre.status).toBe(204);
  });
});

describe("parseRateLimit (unit)", () => {
  it("unset/blank/junk/negative fall back to the default; 0 is an explicit opt-out", () => {
    expect(parseRateLimit(undefined)).toBeGreaterThan(0);
    expect(parseRateLimit("")).toBe(parseRateLimit(undefined));
    expect(parseRateLimit("junk")).toBe(parseRateLimit(undefined));
    expect(parseRateLimit("-3")).toBe(parseRateLimit(undefined));
    expect(parseRateLimit("0")).toBe(0);
    expect(parseRateLimit("5")).toBe(5);
  });
});
