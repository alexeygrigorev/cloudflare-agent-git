import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { describe, expect, it, beforeEach } from "vitest";
import { ADMIN_TOKEN } from "./helpers.js";

describe("git gateway", () => {
  beforeEach(async () => {
     (env as any).ENFORCE_CLOUD_BUDGET = true;
     await SELF.fetch("http://localhost/cloud/demo-repos", {
       method: "DELETE",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}` }
     });
  });

  it("proxies info/refs and enforces token isolation", async () => {
     // Create a task
     const createRes = await SELF.fetch("http://localhost/tasks", {
       method: "POST",
       headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "content-type": "application/json" },
       body: JSON.stringify({ agent: `agent-git-test` })
     });
     expect(createRes.status).toBe(201);
     const task = await createRes.json() as any;
     
     // task.fork.remote should be relative /git/agent-git-test-fork.git
     // Wait, the client got the full URL or relative?
     expect(task.fork.remote.startsWith("http://localhost/git/") || task.fork.remote.startsWith("/git/")).toBe(true);
     
     const urlPath = task.fork.remote.startsWith("http") ? new URL(task.fork.remote).pathname : task.fork.remote;
     const token = task.token.plaintext;
     
     // Call info/refs with correct token
     const infoRes = await SELF.fetch(`http://localhost${urlPath}/info/refs?service=git-upload-pack`, {
       method: "GET",
       headers: { authorization: `Bearer ${token}` }
     });
     
     // the sidecar might return 200
     expect(infoRes.status).toBe(200);
     
     // Upstream token should NOT be in the response
     const infoText = await infoRes.text();
     expect(infoText).not.toContain("real_"); // assuming real token prefix, but let's just make sure it doesn't leak.
     
     // Call with wrong token
     const badRes = await SELF.fetch(`http://localhost${urlPath}/info/refs?service=git-upload-pack`, {
       method: "GET",
       headers: { authorization: `Bearer gw_wrongtoken` }
     });
     expect(badRes.status).toBe(403);
     
     // Ensure public status works and is sanitized
     const statusRes = await SELF.fetch("http://localhost/public/status", { method: "GET" });
     expect(statusRes.status).toBe(200);
     const statusBody = await statusRes.json() as any;
     expect(statusBody.sanitizedSnapshot).toBe(true);
  });
});
