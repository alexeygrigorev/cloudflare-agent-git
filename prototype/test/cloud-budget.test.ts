import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { evictDurableObject } from "cloudflare:test";
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { ADMIN_TOKEN, RUNNER_TOKEN } from "./helpers.js";

async function getBudget(token: string = ADMIN_TOKEN) {
  const res = await SELF.fetch("http://localhost/cloud/budget", {
    headers: { authorization: `Bearer ${token}` }
  });
  if (res.status === 200) return res.json();
  return null;
}

describe("budget constraints", () => {
  beforeEach(async () => {
     (env as any).ENFORCE_CLOUD_BUDGET = true;
     const cleanup = await SELF.fetch("http://localhost/cloud/demo-repos", {
       method: "DELETE",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}` }
     });
     await cleanup.json();
  });

  afterEach(async () => {
     (env as any).ENFORCE_CLOUD_BUDGET = false;
  });

  it("enforces repo count <= 4 and tracks operations", async () => {
     // Create 3 tasks. This creates 1 canonical repo + 3 forks = 4 repos total.
     const responses = [];
     for (let i = 1; i <= 3; i++) {
        responses.push(await SELF.fetch("http://localhost/tasks", {
         method: "POST",
         headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "content-type": "application/json" },
         body: JSON.stringify({ agent: `agent-${i}` })
       }));
     }
     for (const r of responses) {
       expect(r.status).toBe(201);
       await r.json();
     }
     
     // 4th task should fail
     const failRes = await SELF.fetch("http://localhost/tasks", {
       method: "POST",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "content-type": "application/json" },
       body: JSON.stringify({ agent: `agent-4` })
     });
     expect(failRes.status).toBe(429); // 429 for budget exceeded
     await failRes.json();
     
     const stats = await getBudget(ADMIN_TOKEN) as any;
     expect(stats.repoCount).toBe(4);
     expect(stats.utcDayOps).toBeGreaterThanOrEqual(4);
  });
  
  it("persists budget across DO restart", async () => {
     // Run one task to ensure there's a budget count
     const created = await SELF.fetch("http://localhost/tasks", {
       method: "POST",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "content-type": "application/json" },
       body: JSON.stringify({ agent: `agent-restart-1` })
     });
     expect(created.status).toBe(201);
     await created.json();
  
     const before = await getBudget(ADMIN_TOKEN) as any;
     
     const doStub = env.COORDINATOR.get(env.COORDINATOR.idFromName("global"));
     await evictDurableObject(doStub);
     
     const after = await getBudget(ADMIN_TOKEN) as any;
     expect(after.utcDayOps).toBe(before.utcDayOps);
     expect(after.repoCount).toBe(before.repoCount);
  });
  
  it("unauth does not consume operations", async () => {
     const before = await getBudget(ADMIN_TOKEN) as any;
     
     const failRes = await SELF.fetch("http://localhost/tasks", {
       method: "POST",
       headers: { authorization: `Bearer wrong-token`, "content-type": "application/json" },
       body: JSON.stringify({ agent: `agent-unauth` })
     });
     expect(failRes.status).toBe(401);
     await failRes.json();
     
     const after = await getBudget(ADMIN_TOKEN) as any;
     expect(after.utcDayOps).toBe(before.utcDayOps);
  });

  it("admin cleanup", async () => {
     const created = await SELF.fetch("http://localhost/tasks", {
       method: "POST",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "content-type": "application/json" },
       body: JSON.stringify({ agent: `agent-cleanup` })
     });
  
     const delRes = await SELF.fetch("http://localhost/cloud/demo-repos", {
       method: "DELETE",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}` }
     });
     expect(delRes.status).toBe(200);
     const delBody = await delRes.json() as any;
     expect(delBody.deleted).toBeGreaterThan(0);
     
     const stats = await getBudget(ADMIN_TOKEN) as any;
     expect(stats.repoCount).toBe(0);
  });
});
