import { test, expect, describe, vi, beforeEach, afterEach } from "vitest";
import worker from "../src/cloudflare/worker.js";

const DUMMY_ENV = {
  ADMIN_TOKEN: "admin-secret-token",
  MAX_BODY_BYTES: 262144, // 256 KiB
  COORDINATOR: {
    idFromName: () => "global",
    get: () => ({
      resolveGatewayToken: async (token: string, requestedRepo?: string) => {
        if (token === "admin-secret-token") {
          return {
            realToken: "real_admin_upstream",
            upstreamRemote: "https://account123.artifacts.cloudflare.net/git/agent-branches-dev/canonical.git",
            repo: "canonical",
            scope: "write",
          };
        }
        if (token === "gw_valid_write") {
          return {
            realToken: "real_upstream_write",
            upstreamRemote: "https://account123.artifacts.cloudflare.net/git/agent-branches-dev/repo1.git",
            repo: "repo1",
            scope: "write",
          };
        }
        if (token === "gw_readonly") {
          return {
            realToken: "real_upstream_read",
            upstreamRemote: "https://account123.artifacts.cloudflare.net/git/agent-branches-dev/repo1.git",
            repo: "repo1",
            scope: "read",
          };
        }
        if (token === "gw_attacker_domain") {
          return {
            realToken: "real_attacker",
            upstreamRemote: "https://evil.artifacts.cloudflare.net.attacker.com/git/agent-branches-dev/repo1.git",
            repo: "repo1",
            scope: "write",
          };
        }
        if (token === "gw_non_artifacts") {
          return {
            realToken: "real_attacker",
            upstreamRemote: "https://attacker.com/git/repo1.git",
            repo: "repo1",
            scope: "write",
          };
        }
        return null;
      },
      reserveGitOperation: async () => {},
      reserveGitBytes: async () => {},
      getBudgetStats: async () => ({
        utcDayOps: 5,
        calendarMonthOps: 25,
        totalBytesUploaded: 1024,
        repoCount: 2,
        dailyCap: 200,
        monthlyCap: 6000,
        maxRepos: 4,
        maxTotalBytes: 16777216,
        maxBodyBytes: 262144,
        remainingDayOps: 195,
        remainingMonthOps: 5975,
        remainingRepos: 2,
        remainingTotalBytes: 16776192,
      }),
      deleteDemoRepos: async () => 2,
      snapshot: async () => ({
        canonical: { name: "canonical", remote: "/git/canonical.git" },
        agents: [{ agentId: "agent-1", taskId: "task-1", intent: "test", baseSha: "abc" }],
        heads: { "agent-1": "deadbeef" },
        pairs: [],
        warnings: [],
      }),
    }),
  },
} as any;

describe("Worker Git Gateway — Strict Upstream Validation", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("rejects attacker domain masquerading as artifacts with 502", async () => {
    const req = new Request("http://localhost/git/repo1.git/info/refs?service=git-upload-pack", {
      headers: { Authorization: "Bearer gw_attacker_domain" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(502);
    expect(await res.text()).toBe("Invalid upstream remote");
  });

  test("rejects non-artifacts domain with 502", async () => {
    const req = new Request("http://localhost/git/repo1.git/info/refs?service=git-upload-pack", {
      headers: { Authorization: "Bearer gw_non_artifacts" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(502);
  });
});

describe("Worker Git Gateway — Scope & Cross-Repo Access", () => {
  test("cross-repo access is forbidden with 403", async () => {
    const req = new Request("http://localhost/git/other-repo.git/info/refs?service=git-upload-pack", {
      headers: { Authorization: "Bearer gw_valid_write" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(403);
  });

  test("GET info/refs?service=git-receive-pack requires write scope", async () => {
    const req = new Request("http://localhost/git/repo1.git/info/refs?service=git-receive-pack", {
      headers: { Authorization: "Bearer gw_readonly" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(403);
    expect(await res.text()).toBe("Write scope required");
  });

  test("POST git-receive-pack requires write scope", async () => {
    const req = new Request("http://localhost/git/repo1.git/git-receive-pack", {
      method: "POST",
      headers: { Authorization: "Bearer gw_readonly" },
      body: new Uint8Array([1, 2, 3]),
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(403);
  });

  test("invalid or missing action returns 405", async () => {
    const req = new Request("http://localhost/git/repo1.git/info/refs", {
      method: "POST", // invalid method for info/refs
      headers: { Authorization: "Bearer gw_valid_write" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(405);
  });
});

describe("Worker Git Gateway — Request Body Bounds (Streaming <= 256 KiB)", () => {
  test("POST git-receive-pack exceeding 256 KiB is rejected with 413", async () => {
    const oversizedBody = new Uint8Array(256 * 1024 + 1); // 256 KiB + 1
    const req = new Request("http://localhost/git/repo1.git/git-receive-pack", {
      method: "POST",
      headers: {
        Authorization: "Bearer gw_valid_write",
        "Content-Length": String(oversizedBody.byteLength),
      },
      body: oversizedBody,
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(413);
    expect(await res.text()).toBe("Payload too large");
  });

  test("POST git-upload-pack exceeding 256 KiB is rejected with 413", async () => {
    const oversizedBody = new Uint8Array(256 * 1024 + 10);
    const req = new Request("http://localhost/git/repo1.git/git-upload-pack", {
      method: "POST",
      headers: {
        Authorization: "Bearer gw_valid_write",
        "Content-Length": String(oversizedBody.byteLength),
      },
      body: oversizedBody,
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(413);
    expect(await res.text()).toBe("Payload too large");
  });
});

describe("Worker Git Gateway — Header Filtering, No Leaks & No Redirects", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("upstream 302 redirect is rejected with 502 and Location is NOT leaked", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: {
          Location: "https://evil.com/phishing",
          "Set-Cookie": "secret=cookie123",
          Authorization: "Bearer secret-upstream-token",
        },
      }),
    );

    const req = new Request("http://localhost/git/repo1.git/info/refs?service=git-upload-pack", {
      headers: { Authorization: "Bearer gw_valid_write" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(502);
    expect(res.headers.get("Location")).toBeNull();
    expect(res.headers.get("Set-Cookie")).toBeNull();
    expect(res.headers.get("Authorization")).toBeNull();
  });

  test("successful upstream response only forwards allowlisted headers", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("001e# service=git-upload-pack\n0000", {
        status: 200,
        headers: {
          "Content-Type": "application/x-git-upload-pack-advertisement",
          "Cache-Control": "no-cache",
          "cf-ray": "123456789",
          server: "cloudflare",
          "Set-Cookie": "session=sensitive",
        },
      }),
    );

    const req = new Request("http://localhost/git/repo1.git/info/refs?service=git-upload-pack", {
      headers: { Authorization: "Bearer gw_valid_write" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/x-git-upload-pack-advertisement");
    expect(res.headers.get("Cache-Control")).toBe("no-cache");
    expect(res.headers.get("cf-ray")).toBeNull();
    expect(res.headers.get("server")).toBeNull();
    expect(res.headers.get("Set-Cookie")).toBeNull();
  });
});

describe("Worker Management Endpoints — Budget, Cleanup, Public Status", () => {
  test("GET /cloud/budget rejects unauthorized request with 401", async () => {
    const unauthReq = new Request("http://localhost/cloud/budget");
    const res = await worker.fetch(unauthReq, DUMMY_ENV);
    expect(res.status).toBe(401);

    const wrongReq = new Request("http://localhost/cloud/budget", {
      headers: { Authorization: "Bearer wrong-token" },
    });
    const resWrong = await worker.fetch(wrongReq, DUMMY_ENV);
    expect(resWrong.status).toBe(401);
  });

  test("GET /cloud/budget returns flat stats with admin token", async () => {
    const req = new Request("http://localhost/cloud/budget", {
      headers: { Authorization: "Bearer admin-secret-token" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body.utcDayOps).toBe(5);
    expect(body.dailyCap).toBe(200);
    expect(body.remainingDayOps).toBe(195);
  });

  test("DELETE /cloud/demo-repos requires admin and returns deleted count", async () => {
    const req = new Request("http://localhost/cloud/demo-repos", {
      method: "DELETE",
      headers: { Authorization: "Bearer admin-secret-token" },
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body.deleted).toBe(2);
  });

  test("GET /public/status returns sanitized snapshot with absolute canonical URL", async () => {
    const req = new Request("http://localhost:8787/public/status");
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body.sanitizedSnapshot).toBe(true);
    expect(body.canonical.remote).toBe("http://localhost:8787/git/canonical.git");
    expect(body.agents).toBeDefined();
  });

  test("Canonical admin seed endpoint usable via ADMIN token", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("0000", {
        status: 200,
        headers: { "Content-Type": "application/x-git-receive-pack-result" },
      }),
    );
    const req = new Request("http://localhost/git/canonical.git/git-receive-pack", {
      method: "POST",
      headers: { Authorization: "Bearer admin-secret-token" },
      body: new Uint8Array([0, 1, 2]),
    });
    const res = await worker.fetch(req, DUMMY_ENV);
    expect(res.status).toBe(200);
  });
});

describe("Gateway hardening r8", () => {
  test("rejects credential-bearing, port, query, fragment and production loopback upstream URLs without fetching", async () => {
    const original = globalThis.fetch;
    const fetchSpy = vi.fn(); globalThis.fetch = fetchSpy;
    try {
      for (const upstreamRemote of [
        "https://user:pass@acc.artifacts.cloudflare.net/git/agent-branches-dev/repo1.git", // secrets-allow: synthetic user/pass URL tests rejection before any upstream request
        "https://acc.artifacts.cloudflare.net:8443/git/agent-branches-dev/repo1.git",
        "https://acc.artifacts.cloudflare.net/git/agent-branches-dev/repo1.git?secret=yes",
        "https://acc.artifacts.cloudflare.net/git/agent-branches-dev/repo1.git#fragment",
        "http://127.0.0.1:9999/repo1.git",
      ]) {
        const isolated = { ...DUMMY_ENV, ARTIFACTS: {}, COORDINATOR: { idFromName: () => "global", get: () => ({ resolveGatewayToken: async () => ({ repo: "repo1", scope: "write", realToken: "secret", upstreamRemote }) }) } };
        const response = await worker.fetch(new Request("http://localhost/git/repo1.git/info/refs?service=git-upload-pack", { headers: { Authorization: "Bearer gw" } }), isolated as any);
        expect(response.status).toBe(502);
      }
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally { globalThis.fetch = original; }
  });
  test("suppresses upstream error bodies and rejects oversized responses", async () => {
    const original = globalThis.fetch;
    try {
      for (const upstream of [new Response("private-upstream-token", { status: 500 }), new Response("", { headers: { "content-length": String(16777217) } })]) {
        globalThis.fetch = vi.fn().mockResolvedValue(upstream);
        const response = await worker.fetch(new Request("http://localhost/git/repo1.git/info/refs?service=git-upload-pack", { headers: { Authorization: "Bearer gw_valid_write" } }), DUMMY_ENV);
        expect(response.status).toBe(502);
        expect(await response.text()).not.toContain("private-upstream-token");
      }
    } finally { globalThis.fetch = original; }
  });
  test("public status strips task prose, private pair evidence and warning notes", async () => {
    const isolated = { ...DUMMY_ENV, COORDINATOR: { idFromName: () => "global", get: () => ({ snapshot: async () => ({ canonical: { name: "canonical", remote: "/git/canonical.git" }, agents: [{ agentId: "a", taskId: "t", intent: "private-prompt" }], heads: {}, pairs: [{ pair: ["a", "b"], status: "conflict", evidence: "private-evidence" }], warnings: [{ id: "w", status: "active", note: "private-note", acknowledgement: { note: "private-ack" } }] }) }) } };
    const response = await worker.fetch(new Request("http://localhost/public/status"), isolated as any);
    const body = await response.text();
    expect(response.status).toBe(200);
    for (const value of ["private-prompt", "private-evidence", "private-note", "private-ack"]) expect(body).not.toContain(value);
    expect(JSON.parse(body).agents[0].agentId).toBe("a");
  });
});

test("authenticated JSON requests are bounded before coordinator dispatch; unauthorized tasks remains 401", async () => {
  for (const authorized of [false, true]) {
    const request = new Request("http://localhost/tasks", { method: "POST", headers: { "content-type": "application/json", ...(authorized ? { Authorization: "Bearer admin-secret-token" } : {}) }, body: " ".repeat(262145) });
    const response = await worker.fetch(request, DUMMY_ENV);
    expect(response.status).toBe(authorized ? 413 : 401);
  }
});
