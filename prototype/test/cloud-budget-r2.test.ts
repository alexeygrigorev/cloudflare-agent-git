import { test, expect, describe } from "vitest";
import { env } from "cloudflare:workers";
import { runInDurableObject } from "cloudflare:test";
import {
  BudgetTracker,
  BudgetError,
  HARD_CEILINGS,
  parseConfigLimit,
} from "../src/cloudflare/budget.js";
import { Coordinator } from "../src/cloudflare/coordinator-do.js";
import { emptyModel } from "../src/core/model.js";

class FakeTxn {
  private data: Map<string, any>;
  constructor(initialData?: Map<string, any>) {
    this.data = initialData ? new Map(initialData) : new Map();
  }
  async get(key: string) {
    return this.data.get(key);
  }
  async put(key: string, val: any) {
    this.data.set(key, val);
  }
  async delete(key: string) {
    this.data.delete(key);
  }
  async list({ prefix }: { prefix: string }) {
    const map = new Map();
    for (const [k, v] of this.data.entries()) {
      if (k.startsWith(prefix)) map.set(k, v);
    }
    return map;
  }
  getData() {
    return this.data;
  }
}

class FakeStorage {
  public data = new Map<string, any>();
  async get<T = any>(key: string): Promise<T | undefined> {
    return this.data.get(key);
  }
  async put(key: string, val: any): Promise<void> {
    this.data.set(key, val);
  }
  async delete(key: string): Promise<void> {
    this.data.delete(key);
  }
  async list({ prefix }: { prefix: string }): Promise<Map<string, any>> {
    const map = new Map();
    for (const [k, v] of this.data.entries()) {
      if (k.startsWith(prefix)) map.set(k, v);
    }
    return map;
  }
  async transaction<T>(fn: (txn: FakeTxn) => Promise<T>): Promise<T> {
    const txn = new FakeTxn(this.data);
    const result = await fn(txn);
    this.data = txn.getData();
    return result;
  }
}

function makeState(storage = new FakeStorage()) {
  return { storage } as any;
}

describe("BudgetTracker Configuration Validation", () => {
  test("accepts valid lower numeric limits and clamps to hard ceilings", () => {
    const state = makeState();
    const tracker = new BudgetTracker(state, {
      maxDailyOps: 50,
      maxMonthlyOps: 1000,
      maxRepos: 2,
      maxTotalBytes: 1024 * 1024,
      maxBodyBytes: 128 * 1024,
    });
    expect(tracker.config.maxDailyOps).toBe(50);
    expect(tracker.config.maxMonthlyOps).toBe(1000);
    expect(tracker.config.maxRepos).toBe(2);
    expect(tracker.config.maxTotalBytes).toBe(1024 * 1024);
    expect(tracker.config.maxBodyBytes).toBe(128 * 1024);

    // Cannot bypass hard ceilings
    const clamped = new BudgetTracker(state, {
      maxDailyOps: 999999,
      maxMonthlyOps: 999999,
      maxRepos: 99,
      maxTotalBytes: 999999999,
      maxBodyBytes: 999999999,
    });
    expect(clamped.config.maxDailyOps).toBe(HARD_CEILINGS.maxDailyOps);
    expect(clamped.config.maxMonthlyOps).toBe(HARD_CEILINGS.maxMonthlyOps);
    expect(clamped.config.maxRepos).toBe(HARD_CEILINGS.maxRepos);
    expect(clamped.config.maxTotalBytes).toBe(HARD_CEILINGS.maxTotalBytes);
    expect(clamped.config.maxBodyBytes).toBe(HARD_CEILINGS.maxBodyBytes);
  });

  test("rejects NaN, fraction, infinity, and negative limits with 503", () => {
    const state = makeState();
    expect(() => new BudgetTracker(state, { maxDailyOps: NaN })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxDailyOps: 2.5 })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxDailyOps: Infinity })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxDailyOps: -10 })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxMonthlyOps: "invalid" as any })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxRepos: 3.14 })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxTotalBytes: -1 })).toThrowError(BudgetError);
    expect(() => new BudgetTracker(state, { maxBodyBytes: -50 })).toThrowError(BudgetError);
  });
});

describe("BudgetTracker Counter Validation & Corruption Guard", () => {
  test("corrupted null counter in storage fails closed 503", async () => {
    const storage = new FakeStorage();
    const today = new Date().toISOString().split("T")[0];
    await storage.put(`budget:ops:day:${today}`, null); // Corrupted SQLite null

    const tracker = new BudgetTracker(makeState(storage));
    await expect(tracker.reserveOp()).rejects.toThrowError(BudgetError);
    try {
      await tracker.reserveOp();
    } catch (err: any) {
      expect(err.status).toBe(503);
    }
  });

  test("corrupted non-number or negative counter fails closed 503", async () => {
    const storage = new FakeStorage();
    const today = new Date().toISOString().split("T")[0];
    await storage.put(`budget:ops:day:${today}`, "corrupted");

    const tracker = new BudgetTracker(makeState(storage));
    await expect(tracker.reserveOp()).rejects.toThrowError(BudgetError);

    await storage.put(`budget:ops:day:${today}`, -5);
    await expect(tracker.reserveOp()).rejects.toThrowError(BudgetError);
  });

  test("negative requested bytes fail closed 503", async () => {
    const tracker = new BudgetTracker(makeState());
    await expect(tracker.reserveBytes(-1)).rejects.toThrowError(BudgetError);
    await expect(tracker.reserveBytes(NaN)).rejects.toThrowError(BudgetError);
    await expect(tracker.reserveBytes(1.5)).rejects.toThrowError(BudgetError);
  });
});

describe("Budget Operations & Ceilings", () => {
  test("reserves ops up to daily cap, then returns 429", async () => {
    const tracker = new BudgetTracker(makeState(), { maxDailyOps: 3 });
    await tracker.reserveOp();
    await tracker.reserveOp();
    await tracker.reserveOp();

    await expect(tracker.reserveOp()).rejects.toThrowError(/Budget exceeded: max daily ops/);
    try {
      await tracker.reserveOp();
    } catch (err: any) {
      expect(err.status).toBe(429);
    }
  });

  test("reserves bytes up to maxTotalBytes, then returns 429", async () => {
    const tracker = new BudgetTracker(makeState(), { maxTotalBytes: 1000 });
    await tracker.reserveBytes(600);
    await tracker.reserveBytes(300);

    await expect(tracker.reserveBytes(200)).rejects.toThrowError(/Budget exceeded: max total bytes/);
    try {
      await tracker.reserveBytes(200);
    } catch (err: any) {
      expect(err.status).toBe(429);
    }
  });

  test("flat stats reporting with caps and remaining fields", async () => {
    const tracker = new BudgetTracker(makeState(), { maxDailyOps: 10, maxMonthlyOps: 100, maxRepos: 4, maxTotalBytes: 5000 });
    await tracker.reserveOp();
    await tracker.reserveBytes(1500);

    const stats = await tracker.getStats();
    expect(stats.utcDayOps).toBe(1);
    expect(stats.calendarMonthOps).toBe(1);
    expect(stats.totalBytesUploaded).toBe(1500);
    expect(stats.repoCount).toBe(0);
    expect(stats.dailyCap).toBe(10);
    expect(stats.monthlyCap).toBe(100);
    expect(stats.maxRepos).toBe(4);
    expect(stats.maxTotalBytes).toBe(5000);
    expect(stats.remainingDayOps).toBe(9);
    expect(stats.remainingMonthOps).toBe(99);
    expect(stats.remainingRepos).toBe(4);
    expect(stats.remainingTotalBytes).toBe(3500);
  });
});

describe("Atomic Repo Slot Reservation", () => {
  test("persists pending slot atomically and enforces max 4 repos limit", async () => {
    const storage = new FakeStorage();
    const tracker = new BudgetTracker(makeState(storage), { maxRepos: 4 });

    // Reserve 4 slots
    await tracker.reserveRepoSlot("repo1");
    await tracker.reserveRepoSlot("repo2");
    await tracker.reserveRepoSlot("repo3");
    await tracker.reserveRepoSlot("repo4");

    // All 4 are persisted in storage as pending
    expect(await storage.get("repo:repo1:pending")).toBeDefined();
    expect(await storage.get("repo:repo2:pending")).toBeDefined();
    expect(await storage.get("repo:repo3:pending")).toBeDefined();
    expect(await storage.get("repo:repo4:pending")).toBeDefined();

    // Stats reflect 4 repos
    const stats = await tracker.getStats();
    expect(stats.repoCount).toBe(4);
    expect(stats.remainingRepos).toBe(0);

    // Attempting 5th repo throws 429
    await expect(tracker.reserveRepoSlot("repo5")).rejects.toThrowError(/Budget exceeded: max repos/);

    // Attempting to reserve the same repo name again fails closed
    await expect(tracker.reserveRepoSlot("repo1")).rejects.toThrowError(/Repo slot already reserved/);
  });
});

describe("Token Expiration and Revocation Integration in Coordinator DO", () => {
  test("token expiry parsed correctly from ISO string", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("test-expiry"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const storage = state.storage;
      const repo = "canonical-seed-repo";
      await storage.put(`repo:${repo}:upstream`, "https://example.com");
      
      // 1. Expired token (past ISO date) negative
      const taskExpired = await coordinator.createTask({ agent: "expired-agent" });
      const gwExpired = taskExpired.token!.plaintext;
      await storage.put(`repo:${taskExpired.fork.name}:upstream`, taskExpired.fork.remote);
      await storage.put(`token:${gwExpired}`, {
        realToken: "real_123",
        repo: taskExpired.fork.name,
        scope: "write",
        expiresAt: new Date(Date.now() - 60000).toISOString(),
        agentId: taskExpired.agentId,
      });
      expect(await coordinator.resolveGatewayToken(gwExpired)).toBeNull();
      
      // 2. Orphan missing agent rejection
      const taskOrphan = await coordinator.createTask({ agent: "orphan-agent" });
      const gwOrphan = taskOrphan.token!.plaintext;
      await storage.put(`repo:${taskOrphan.fork.name}:upstream`, taskOrphan.fork.remote);
      await storage.put(`token:${gwOrphan}`, {
        realToken: "real_123",
        repo: taskOrphan.fork.name,
        scope: "write",
        expiresAt: new Date(Date.now() + 60000).toISOString(),
        // missing agentId
      });
      expect(await coordinator.resolveGatewayToken(gwOrphan)).toBeNull();
      
      // 3. Mismatched agent
      const taskMismatch = await coordinator.createTask({ agent: "mismatch-agent" });
      const gwMismatch = taskMismatch.token!.plaintext;
      await storage.put(`repo:${taskMismatch.fork.name}:upstream`, taskMismatch.fork.remote);
      await storage.put(`token:${gwMismatch}`, {
        realToken: "real_123",
        repo: taskMismatch.fork.name,
        scope: "write",
        expiresAt: new Date(Date.now() + 60000).toISOString(),
        agentId: "some-other-agent",
      });
      expect(await coordinator.resolveGatewayToken(gwMismatch)).toBeNull();

      // 4. Valid token from createTask mapping preserves positive assertion
      const taskValid = await coordinator.createTask({ agent: "valid-agent" });
      const gwValid = taskValid.token!.plaintext;
      await storage.put(`repo:${taskValid.fork.name}:upstream`, taskValid.fork.remote);
      await storage.put(`token:${gwValid}`, {
        realToken: "real_123",
        repo: taskValid.fork.name,
        scope: "write",
        expiresAt: new Date(Date.now() + 60000).toISOString(),
        agentId: taskValid.agentId,
      });
      const resolved = await coordinator.resolveGatewayToken(gwValid);
      expect(resolved).not.toBeNull();
      expect(resolved?.realToken).toBe("real_123");
      expect(resolved?.scope).toBe("write");
    });
  });

  test("revoking an agent in core revokes all associated gateway tokens", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("test-revoke"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const task = await coordinator.createTask({ agent: "agent-target" });
      const gwToken = task.token!.plaintext;

      // Revoke the agent via coordinator
      await coordinator.revokeAgentToken("agent-target");

      // Gateway token is now marked revoked and resolveGatewayToken returns null
      const afterRevoke = await coordinator.resolveGatewayToken(gwToken);
      expect(afterRevoke).toBeNull();
    });
  });

  test("admin seed access resolves canonical repo via ADMIN_TOKEN", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("test-admin-seed"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const storage = state.storage;
      // Set canonical repo
      await storage.put("canonical:repo", "canonical-seed-repo");
      await storage.put("repo:canonical-seed-repo:upstream", "https://acc.artifacts.cloudflare.net/git/agent-branches-dev/canonical-seed-repo.git");
      await storage.put("canonical:token", "gw_canonical_init");
      await storage.put("token:gw_canonical_init", {
        realToken: "real_seed_token",
        repo: "canonical-seed-repo",
        scope: "write",
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      });

      const resolved = await coordinator.resolveGatewayToken("test-admin-token", "canonical-seed-repo");
      expect(resolved).not.toBeNull();
      expect(resolved?.repo).toBe("canonical-seed-repo");
      expect(resolved?.realToken).toBe("real_seed_token");
      
      // expired/malformed/revoked canonical credential negatives
      await storage.put("token:gw_canonical_init", {
        realToken: "real_seed_token",
        repo: "canonical-seed-repo",
        scope: "write",
        expiresAt: new Date(Date.now() - 3600000).toISOString(), // expired
      });
      expect(await coordinator.resolveGatewayToken("test-admin-token", "canonical-seed-repo")).toBeNull();
      
      await storage.put("token:gw_canonical_init", {
        realToken: "real_seed_token",
        repo: "canonical-seed-repo",
        scope: "write",
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
        revoked: true,
      });
      expect(await coordinator.resolveGatewayToken("test-admin-token", "canonical-seed-repo")).toBeNull();

      // canonical blank/invalid realToken, wrongstoredrepo and readonlyscope negative cases
      await storage.put("token:gw_canonical_init", {
        realToken: "",
        repo: "canonical-seed-repo",
        scope: "write",
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      });
      expect(await coordinator.resolveGatewayToken("test-admin-token", "canonical-seed-repo")).toBeNull();

      await storage.put("token:gw_canonical_init", {
        realToken: "real_seed_token",
        repo: "wrong-stored-repo",
        scope: "write",
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      });
      expect(await coordinator.resolveGatewayToken("test-admin-token", "canonical-seed-repo")).toBeNull();

      await storage.put("token:gw_canonical_init", {
        realToken: "real_seed_token",
        repo: "canonical-seed-repo",
        scope: "read",
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      });
      expect(await coordinator.resolveGatewayToken("test-admin-token", "canonical-seed-repo")).toBeNull();
    });
  });

  test("task gateway auth ensures token repo belongs to credential agent", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("test-task-auth"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const storage = state.storage;
      
      // create TWO genuine tasks/agents/forks using maintained core
      await coordinator.setup();
      const task1 = await coordinator.createTask({ agent: "agent-1" });
      const task2 = await coordinator.createTask({ agent: "agent-2" });
      
      const fork1 = task1.fork.name;
      const fork2 = task2.fork.name;
      
      // Add upstream records
      await storage.put(`repo:${fork1}:upstream`, task1.fork.remote);
      await storage.put(`repo:${fork2}:upstream`, task2.fork.remote);
      
      const gw1 = task1.token!.plaintext;

      await storage.put(`token:${gw1}`, {
        realToken: "real_123",
        repo: fork1,
        scope: "write",
        expiresAt: new Date(Date.now() + 60000).toISOString(),
        agentId: task1.agentId,
      });
      
      // valid token positive assertion
      let resolved = await coordinator.resolveGatewayToken(gw1, fork1);
      expect(resolved).not.toBeNull();
      expect(resolved?.repo).toBe(fork1);
      
      // mutate tokenInfo.repo to second existingfork AND request that secondfork; deny
      const tokenRecord = await storage.get<any>(`token:${gw1}`);
      tokenRecord.repo = fork2;
      await storage.put(`token:${gw1}`, tokenRecord);
      
      resolved = await coordinator.resolveGatewayToken(gw1, fork2);
      expect(resolved).toBeNull();
    });
  });

  test("cleanup clears inventory, credentials, and core cache but NEVER resets budget counters", async () => {
    (env as any).ENFORCE_CLOUD_BUDGET = true;
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("test-cleanup"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const storage = state.storage;
      // Set up operations in budget
      await coordinator.reserveGitOperation();
      await coordinator.reserveGitOperation();
      await coordinator.reserveGitBytes(2048);

      // Set up demo repos and tokens
      await storage.put("repo:demo1:upstream", "http://127.0.0.1:4000/git/demo1.git");
      await storage.put("repo:demo2:upstream", "http://127.0.0.1:4000/git/demo2.git");
      await storage.put("token:gw1", { repo: "demo1", realToken: "rt1" });
      await storage.put("token:gw2", { repo: "demo2", realToken: "rt2" });
      await storage.put("canonical:repo", "demo2");
      await storage.put("canonical:token", "gw2");
      await storage.put("canonical:upstream_token", "legacysecret");
      const model = emptyModel();
      model.canonicalName = "demo2";
      model.demoRuns["a".repeat(32)] = { canonical: "demo2", repositories: ["demo1", "demo2"], complete: false };
      await storage.put("model", model);

      // Perform cleanup
      const deleted = await coordinator.deleteDemoRepos("a".repeat(32));
      expect(deleted.complete).toBe(true);

      // Verify tokens, model, and repos are cleared
      expect(await storage.get("canonical:repo")).toBeUndefined();
      expect(await storage.get("canonical:token")).toBeUndefined();
      expect(await storage.get("canonical:upstream_token")).toBeUndefined();
      expect(await storage.get("token:gw1")).toBeUndefined();
      expect(await storage.get("token:gw2")).toBeUndefined();
      expect((await storage.get<any>("model")).demoRuns["a".repeat(32)].complete).toBe(true);

      // BUDGET COUNTERS ARE PRESERVED! NEVER RESET!
      const stats = await coordinator.getBudgetStats();
      expect(stats.utcDayOps).toBeGreaterThanOrEqual(2);
      expect(stats.totalBytesUploaded).toBe(2048);
      expect(stats.repoCount).toBe(0);
    });
  });
  
  test("cleanup partial failure/budget exhaustion inventory/token preservation case", async () => {
    (env as any).ENFORCE_CLOUD_BUDGET = true;
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("test-cleanup-partial"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const storage = state.storage;
      
      await storage.put("repo:demo1:upstream", "http://127.0.0.1:4000/git/demo1.git");
      await storage.put("repo:demo2:upstream", "http://127.0.0.1:4000/git/demo2.git");
      await storage.put("token:gw1", { repo: "demo1", realToken: "rt1" });
      await storage.put("token:gw2", { repo: "demo2", realToken: "rt2" });
      await storage.put("canonical:repo", "demo2");
      await storage.put("canonical:token", "gw2");
      const model = emptyModel();
      model.canonicalName = "demo2";
      model.demoRuns["a".repeat(32)] = { canonical: "demo2", repositories: ["demo1", "demo2"], complete: false };
      await storage.put("model", model);
      
      // Exhaust budget ops so deleteRepo fails mid-way
      const stats = await coordinator.getBudgetStats();
      const dailyCap = stats.dailyCap;
      const now = new Date();
      const pad = (n: number) => n.toString().padStart(2, "0");
      const day = `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())}`;
      await storage.put(`budget:ops:day:${day}`, dailyCap - 1);
      // deleteDemoRepos will reserve 1 op for demo1 (making it 500) and then fail on demo2
      let error;
      try {
        await coordinator.deleteDemoRepos("a".repeat(32));
      } catch (e) {
        error = e;
      }
      expect(error).toBeDefined();
      expect((error as Error).message).toMatch(/Budget exceeded/);
      
      // Tokens for deleted repos are cleared, but demo2 remains
      const gw2 = await storage.get("token:gw2");
      expect(gw2).toBeDefined();
      
      // Canonical stays since demo2 remains
      expect(await storage.get("canonical:repo")).toBe("demo2");
    });
  });
});

describe("Malformed persisted gateway credentials fail closed", () => {
  test("rejects missing, zero, null and malformed expiry and invalid scope", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("malformed-expiry-r8"));
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      await state.storage.put("repo:r8:upstream", "https://acc.artifacts.cloudflare.net/git/agent-branches-dev/r8.git");
      for (const expiresAt of [undefined, 0, null, false, "invalid", ""]) {
        await state.storage.put("token:gw_r8", { realToken: "secret", repo: "r8", scope: "write", ...(expiresAt === undefined ? {} : { expiresAt }) });
        expect(await coordinator.resolveGatewayToken("gw_r8", "r8")).toBeNull();
      }
      await state.storage.put("token:gw_r8", { realToken: "secret", repo: "r8", scope: "admin", expiresAt: new Date(Date.now()+60000).toISOString() });
      expect(await coordinator.resolveGatewayToken("gw_r8", "r8")).toBeNull();
    });
  });
});
