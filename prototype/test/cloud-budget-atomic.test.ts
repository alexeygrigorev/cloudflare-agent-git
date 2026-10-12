import { env } from "cloudflare:workers";
import { evictDurableObject, runInDurableObject } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import type { Coordinator } from "../src/cloudflare/coordinator-do.js";
import { RealArtifacts, type ArtifactsNamespaceBinding, type ArtifactsRepoCapability } from "../src/artifacts/real.js";

describe("persistent budget safety at actual boundaries", () => {
  it("allows only one concurrent attempt at both hard limits and survives eviction", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("atomic-limit-test"));
    const now = new Date().toISOString();
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      await state.storage.put("budget:ops:day:" + now.slice(0, 10), 199);
      await state.storage.put("budget:ops:month:" + now.slice(0, 7), 5999);
      const attempts = await Promise.allSettled(
        Array.from({ length: 24 }, () => coordinator.reserveGitOperation()),
      );
      expect(attempts.filter(result => result.status === "fulfilled")).toHaveLength(1);
      expect(attempts.filter(result => result.status === "rejected")).toHaveLength(23);
      expect(await coordinator.getBudgetStats()).toMatchObject({
        utcDayOps: 200, calendarMonthOps: 6000,
      });
    });
    await evictDurableObject(stub);
    await runInDurableObject(stub, async (coordinator: Coordinator) => {
      expect(await coordinator.getBudgetStats()).toMatchObject({
        utcDayOps: 200, calendarMonthOps: 6000,
      });
      await expect(coordinator.reserveGitOperation()).rejects.toThrow(/Budget exceeded/);
    });
  });

  it("refuses a corrupt persisted monthly counter without incrementing the day", async () => {
    const stub = env.COORDINATOR.get(env.COORDINATOR.idFromName("corrupt-month-test"));
    const now = new Date().toISOString();
    await runInDurableObject(stub, async (coordinator: Coordinator, state: DurableObjectState) => {
      const day = "budget:ops:day:" + now.slice(0, 10);
      await state.storage.put(day, 7);
      await state.storage.put("budget:ops:month:" + now.slice(0, 7), null);
      await expect(coordinator.reserveGitOperation()).rejects.toThrow(/Corrupted counter/);
      expect(await state.storage.get(day)).toBe(7);
    });
  });

  it("reserves before every capability and readiness call, including failed calls", async () => {
    const events: string[] = [];
    let reservations = 0;
    let calls = 0;
    const called = (name: string) => {
      calls++;
      events.push(name);
      expect(reservations).toBe(calls);
    };
    const capability = {
      fork: async () => {
        called("fork");
        return { name: "forked", remote: "https://account.artifacts.cloudflare.net/git/agent-branches-dev/forked.git", defaultBranch: "main", token: "fake-private-token" };
      },
      createToken: async () => {
        called("token");
        throw new Error("provider failure");
      },
      [Symbol.dispose]: () => events.push("dispose"),
    } as unknown as ArtifactsRepoCapability;
    let polls = 0;
    const binding = {
      get: async () => { called("get"); return capability; },
      list: async () => {
        called("poll"); polls++;
        return { repos: [{ name: "forked", status: polls === 2 ? "ready" : "forking" }] };
      },
    } as unknown as ArtifactsNamespaceBinding;
    const adapter = new RealArtifacts(binding, {
      beforeOperation: async () => { reservations++; events.push("reserve"); },
      readiness: { maxAttempts: 3, delayMs: 0 },
      sleep: async () => {},
    });
    await adapter.fork("source", "forked");
    await expect(adapter.mintToken("forked")).rejects.toThrow("provider failure");
    expect(reservations).toBe(6);
    expect(calls).toBe(6);
    expect(events).toEqual([
      "reserve", "get", "reserve", "fork", "reserve", "poll", "reserve", "poll", "dispose",
      "reserve", "get", "reserve", "token", "dispose",
    ]);
  });

  it("does not touch the provider when the pre-call reservation refuses", async () => {
    let calls = 0;
    const binding = { get: async () => { calls++; throw new Error("must not reach provider"); } } as unknown as ArtifactsNamespaceBinding;
    const adapter = new RealArtifacts(binding, { beforeOperation: async () => { throw new Error("budget exhausted"); } });
    await expect(adapter.mintToken("source")).rejects.toThrow("budget exhausted");
    expect(calls).toBe(0);
  });
});
