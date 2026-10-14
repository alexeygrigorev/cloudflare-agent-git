import { describe, expect, test } from "vitest";
import { BudgetAwareGitHost } from "../src/cloudflare/budget-githost.js";
import worker from "../src/cloudflare/worker.js";

class Store {
  data = new Map<string, any>();
  async get(key: string) { return this.data.get(key); }
  async put(key: string, value: any) { this.data.set(key, value); }
  async delete(key: string) { return this.data.delete(key); }
  async list({ prefix }: { prefix: string }) { return new Map([...this.data].filter(([key]) => key.startsWith(prefix))); }
  async transaction(fn: (txn: Store) => Promise<void>) { await fn(this); }
}

describe("owned cleanup adapter boundaries", () => {
  test("delete scrubs only exact repo records and credentials, including already-absent repos", async () => {
    const storage = new Store();
    for (const name of ["own", "peer"]) {
      await storage.put(`repo:${name}:upstream`, `https://invalid/${name}`);
      await storage.put(`repo:${name}:pending`, true);
      await storage.put(`token:${name}`, { repo: name });
    }
    await storage.put("canonical:repo", "peer");
    await storage.put("canonical:token", "peer-token");
    await storage.put("budget:private-counter", 71);
    let reservations = 0;
    const adapter = new BudgetAwareGitHost({ deleteRepo: async () => false } as any,
      { reserveOp: async () => { reservations++; } } as any, { storage } as any);
    await adapter.deleteRepo("own");
    expect(reservations).toBe(1);
    expect(await storage.get("repo:own:upstream")).toBeUndefined();
    expect(await storage.get("repo:own:pending")).toBeUndefined();
    expect(await storage.get("token:own")).toBeUndefined();
    expect(await storage.get("token:peer")).toEqual({ repo: "peer" });
    expect(await storage.get("canonical:repo")).toBe("peer");
    expect(await storage.get("canonical:token")).toBe("peer-token");
    expect(await storage.get("budget:private-counter")).toBe(71);
  });

  test("budget failure preserves owned inventory and gateway credentials", async () => {
    const storage = new Store();
    await storage.put("repo:own:pending", true);
    await storage.put("token:own", { repo: "own" });
    let deletions = 0;
    const adapter = new BudgetAwareGitHost({ deleteRepo: async () => { deletions++; return true; } } as any,
      { reserveOp: async () => { throw new Error("Budget exceeded"); } } as any, { storage } as any);
    await expect(adapter.deleteRepo("own")).rejects.toThrow("Budget exceeded");
    expect(deletions).toBe(0);
    expect(await storage.get("repo:own:pending")).toBe(true);
    expect(await storage.get("token:own")).toEqual({ repo: "own" });
  });

  test("inventory includes pending peer creation omitted from provider list", async () => {
    const storage = new Store();
    await storage.put("repo:peer-pending:pending", true);
    const adapter = new BudgetAwareGitHost({ listRepos: async () => [{ name: "own", status: "ready" }] } as any,
      { reserveOp: async () => {} } as any, { storage } as any);
    expect((await adapter.listRepos()).map((repo) => repo.name).sort()).toEqual(["own", "peer-pending"]);
  });

  test("Worker refuses unauthenticated, invalid, bodyless and non-DELETE cleanup before RPC", async () => {
    let called = 0;
    const env = { ADMIN_TOKEN: "admin", COORDINATOR: { idFromName: () => "global", get: () => ({
      deleteDemoRepos: async () => { called++; return { complete: true }; },
    }) } } as any;
    for (const token of [undefined, "wrong", "runner"]) {
      const response = await worker.fetch(new Request("https://offline.invalid/cloud/demo-repos", {
        method: "DELETE", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: JSON.stringify({ runId: "a".repeat(32) }),
      }), env);
      expect(response.status).toBe(401);
    }
    expect((await worker.fetch(new Request("https://offline.invalid/cloud/demo-repos", {
      headers: { Authorization: "Bearer admin" },
    }), env)).status).toBe(405);
    for (const body of [undefined, "{}", '{"runId":"bad"}', "null"]) {
      expect((await worker.fetch(new Request("https://offline.invalid/cloud/demo-repos", {
        method: "DELETE", headers: { Authorization: "Bearer admin" }, body,
      }), env)).status).toBe(400);
    }
    expect(called).toBe(0);
    expect((await worker.fetch(new Request("https://offline.invalid/cloud/demo-repos", {
      method: "DELETE", headers: { Authorization: "Bearer admin" }, body: JSON.stringify({ runId: "a".repeat(32) }),
    }), env)).status).toBe(200);
    expect(called).toBe(1);
  });
});
