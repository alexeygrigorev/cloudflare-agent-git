import { env, runInDurableObject, SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { logSafe, REDACTED, redact } from "../src/redact.js";
import { ADMIN_TOKEN, RUNNER_TOKEN, SIDECAR_TOKEN } from "./helpers.js";

const EVENT = {
  type: "cf.artifacts.repo.pushed",
  source: { type: "artifacts.repo", namespace: "local", repoName: "who-knows" },
  payload: { ref: "refs/heads/main", after: "a".repeat(40) },
};

async function post(path: string, body: unknown, token?: string): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) {
    headers.authorization = `Bearer ${token}`;
  }
  return SELF.fetch(`http://localhost${path}`, { method: "POST", headers, body: JSON.stringify(body) });
}

async function createTask(agent: string): Promise<{ taskId: string; agentId: string; token: { plaintext: string } }> {
  const res = await post("/tasks", { agent }, ADMIN_TOKEN);
  expect(res.status).toBe(201);
  return (await res.json()) as { taskId: string; agentId: string; token: { plaintext: string } };
}

/**
 * §5.1 sweep: no mutating route may be reachable without a bearer token —
 * including id-carrying routes, which must 401 BEFORE any existence check so
 * an unauthenticated caller cannot enumerate task/warning ids.
 */
describe("auth sweep over every mutating route (§5.1)", () => {
  const MUTATING: Array<[string, unknown]> = [
    ["/setup", {}],
    ["/tasks", { agent: "sweep" }],
    ["/events/push", { agent: "sweep", sha: "c".repeat(40) }],
    ["/events/artifacts", EVENT],
    ["/checks", { policy: "p", results: [] }],
    ["/tasks/task-does-not-exist/tests", { command: "npm test", exit: 0, head_sha: "d".repeat(40) }],
    ["/warnings/warn-does-not-exist/ack", { agent: "sweep" }],
  ];

  it("every mutating route is 401 with no bearer token", async () => {
    for (const [path, body] of MUTATING) {
      const res = await post(path, body);
      expect(res.status, path).toBe(401);
      const text = await res.text();
      expect(text).not.toContain(ADMIN_TOKEN);
    }
  });

  it("a wrong bearer never grants access either", async () => {
    for (const [path, body] of MUTATING) {
      const res = await post(path, body, "definitely-not-a-real-token");
      // The id-carrying routes resolve existence for token-holders by design
      // (owner scoping needs the id; task ids are public via GET /tasks/:id).
      expect([401, 404], path).toContain(res.status);
      if (res.status === 401) {
        expect(await res.text()).not.toContain("definitely-not-a-real-token");
      }
    }
  });
});

/**
 * §5.2 token-at-rest: minted repo tokens and shared secrets live ONLY as
 * SHA-256 digests (or env vars) — the DO storage must never hold a plaintext.
 * The one-time plaintext handoff to its owner (createTask response) is the
 * deliberate exception; every later read must be plaintext-free.
 */
describe("token-at-rest (§5.2)", () => {
  it("DO storage never contains shared secrets or minted task tokens", async () => {
    const a = await createTask("rest-a");
    const b = await createTask("rest-b");
    const dump = await runInDurableObject(
      env.COORDINATOR.get(env.COORDINATOR.idFromName("global")),
      async (_instance, state) => {
        const entries: unknown[] = [];
        for (const [key, value] of await state.storage.list()) {
          entries.push([key, value]);
        }
        return JSON.stringify(entries);
      },
    );
    for (const secret of [ADMIN_TOKEN, RUNNER_TOKEN, SIDECAR_TOKEN, a.token.plaintext, b.token.plaintext]) {
      expect(dump).not.toContain(secret);
    }
    // The at-rest form is a 64-hex digest keyed by owning agent (§5.2).
    expect(dump).toMatch(new RegExp(`"${a.agentId}":"[0-9a-f]{64}"`));
    expect(dump).toMatch(new RegExp(`"${b.agentId}":"[0-9a-f]{64}"`));
  });

  it("the minted plaintext appears exactly once — never on later reads", async () => {
    const created = await createTask("rest-once");
    for (const path of [`/tasks/${created.taskId}`, "/status"]) {
      const res = await SELF.fetch(`http://localhost${path}`);
      expect(res.status).toBe(200);
      expect(await res.text()).not.toContain(created.token.plaintext);
    }
  });
});

/** §5.2/§5.6: the redactor is the only sanctioned path to any log sink. */
describe("logging redaction", () => {
  const artifactsToken = `art_v2_x_${"ab12cd34".repeat(5)}?expires=1791051501`;

  it("strips artifacts tokens, Authorization headers, bearer values and account URLs", () => {
    const secrets = [ADMIN_TOKEN, RUNNER_TOKEN, SIDECAR_TOKEN];
    const headerLine = redact(`POST /tasks authorization: Bearer ${artifactsToken}`, secrets);
    expect(headerLine).not.toContain("ab12cd34");
    expect(headerLine).toContain(REDACTED);

    const shared = redact(`auth failure: authorization: Bearer ${ADMIN_TOKEN}`, secrets);
    expect(shared).not.toContain(ADMIN_TOKEN);
    expect(shared).toContain("authorization: Bearer [REDACTED]");

    const jsonish = redact(`{"authorization":"Bearer ${SIDECAR_TOKEN}"}`, secrets);
    expect(jsonish).not.toContain(SIDECAR_TOKEN);

    const standalone = redact(`presented bearer ${RUNNER_TOKEN} was rejected`, secrets);
    expect(standalone).not.toContain(RUNNER_TOKEN);

    const remote = redact(
      "fork remote https://abcdef0123456789abcdef0123456789.artifacts.cloudflare.net/demo-canonical",
    );
    expect(remote).toBe("fork remote https://<account>.artifacts.cloudflare.net/demo-canonical");
  });

  it("catches future token versions and shapeless shared secrets passed explicitly", () => {
    const future = `art_v9_q_${"deadbeef".repeat(5)}`;
    const out = redact(`token=${future}`, [RUNNER_TOKEN]);
    expect(out).not.toContain(future);
    expect(out).toContain(REDACTED);
  });

  it("short strings are never treated as exact-match secrets", () => {
    expect(redact("abc def", ["abc"])).toBe("abc def");
  });

  it("logSafe redacts before anything reaches the console", () => {
    const original = console.error;
    let captured = "";
    console.error = (line: unknown) => {
      captured = String(line);
    };
    try {
      logSafe([RUNNER_TOKEN], "auth failure:", `authorization: Bearer ${RUNNER_TOKEN}`);
    } finally {
      console.error = original;
    }
    expect(captured).not.toContain(RUNNER_TOKEN);
    expect(captured).toContain(REDACTED);
  });
});
