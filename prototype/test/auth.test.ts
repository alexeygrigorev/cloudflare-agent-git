import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const ADMIN = "test-admin-token";
const RUNNER = "test-runner-token";

function post(path: string, body: unknown, token?: string): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) {
    headers.authorization = `Bearer ${token}`;
  }
  return SELF.fetch(`http://localhost${path}`, { method: "POST", headers, body: JSON.stringify(body) });
}

async function bodyText(response: Response): Promise<string> {
  return await response.text();
}

describe("auth (codex C-1305 #3)", () => {
  it("POST /tasks requires the admin bearer token", async () => {
    const noToken = await post("/tasks", { agent: "authless" });
    expect(noToken.status).toBe(401);

    const wrongToken = await post("/tasks", { agent: "authless" }, "definitely-not-the-admin-token");
    expect(wrongToken.status).toBe(401);

    // Never echo the presented token in the error body.
    const text = await bodyText(wrongToken);
    expect(text).not.toContain("definitely-not-the-admin-token");

    const rightToken = await post("/tasks", { agent: "authok" }, ADMIN);
    expect(rightToken.status).toBe(201);
  });

  it("POST /setup requires the admin bearer token", async () => {
    const denied = await post("/setup", {});
    expect(denied.status).toBe(401);
    const allowed = await post("/setup", {}, ADMIN);
    expect(allowed.status).toBe(201);
  });

  it("the admin token does not grant the runner route and vice versa", async () => {
    const adminOnRunner = await post("/checks", { policy: "p", results: [] }, ADMIN);
    expect(adminOnRunner.status).toBe(401);

    const noToken = await post("/checks", { policy: "p", results: [] });
    expect(noToken.status).toBe(401);

    // Correct runner token passes auth (then fails on the empty body shape).
    const runnerOk = await post("/checks", { policy: "p" }, RUNNER);
    expect(runnerOk.status).toBe(400);
  });

  it("401 bodies never contain the presented token", async () => {
    const secretAttempt = "art_v1_leaked_attempt_0000000000000000000000";
    const response = await post("/tasks", { agent: "x" }, secretAttempt);
    expect(response.status).toBe(401);
    const text = await bodyText(response);
    expect(text).not.toContain(secretAttempt);
  });

  it("read routes stay open", async () => {
    const status = await SELF.fetch("http://localhost/status");
    expect(status.status).toBe(200);
  });
});
