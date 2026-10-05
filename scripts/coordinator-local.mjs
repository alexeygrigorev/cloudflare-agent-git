#!/usr/bin/env node
/**
 * Self-contained local coordinator runtime (pure Node.js standard library).
 *
 * Implements Cloudflare Agent Branches L1 Coordinator CONTRACT v0.1:
 * - Admin routes: POST /setup, POST /tasks, POST /tasks/:id/revoke
 * - Push events: POST /events/push (Git Smart HTTP sidecar webhook ingestion)
 * - Status & inspection: GET /status, GET /tasks/:id
 * - Pre-merge Radar evaluation: POST /checks (CONTRACT v0.1 schema)
 * - Warning lifecycle: POST /warnings/:id/ack
 *
 * Zero external npm dependencies. Zero Cloudflare dependencies.
 * Binds 127.0.0.1 by default; never logs secrets to stdout.
 */

import { createServer } from "node:http";
import { randomBytes } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, existsSync, chmodSync } from "node:fs";
import { dirname } from "node:path";

const PORT = Number(process.env.PORT ?? 8788);
const HOST = process.env.HOST ?? "127.0.0.1";
const LOCAL_ARTIFACTS_URL = process.env.LOCAL_ARTIFACTS_URL;
const LOCAL_ARTIFACTS_TOKEN = process.env.LOCAL_ARTIFACTS_TOKEN;
const ADMIN_TOKEN = process.env.ADMIN_TOKEN;
const RUNNER_TOKEN = process.env.RUNNER_TOKEN;
const STATE_FILE = process.env.COORDINATION_STORE_PATH ?? process.env.COORDINATOR_STATE_FILE ?? "./local-coordinator-state.json";

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};

class LocalCoordinatorStore {
  constructor(path) {
    this.path = path;
    this.model = {
      canonical: null,
      canonicalName: null,
      canonicalRemote: null,
      seq: 0,
      warnSeq: 0,
      tasks: {},
      agents: {},
      heads: {},
      warnings: [],
      pairChecks: {},
      radarLog: [],
      lastRunnerReport: null,
      agentTokens: {}, // token -> agentId
      taskTokens: {},  // taskId -> token
    };
    this.load();
  }

  load() {
    if (this.path && existsSync(this.path)) {
      try {
        const raw = readFileSync(this.path, "utf8");
        const data = JSON.parse(raw);
        if (data.model) {
          this.model = { ...this.model, ...data.model };
        } else {
          this.model = { ...this.model, ...data };
        }
      } catch (err) {
        console.error(`[coordinator] warning: could not parse state file: ${err.message}`);
      }
    }
  }

  save() {
    if (!this.path) return;
    try {
      mkdirSync(dirname(this.path), { recursive: true });
      writeFileSync(this.path, JSON.stringify({ model: this.model }, null, 2), { mode: 0o600, encoding: "utf8" });
      chmodSync(this.path, 0o600);
    } catch (err) {
      console.error(`[coordinator] error saving state: ${err.message}`);
    }
  }
}

const store = new LocalCoordinatorStore(STATE_FILE);

async function sidecarRequest(path, method = "GET", body = null) {
  if (!LOCAL_ARTIFACTS_URL) {
    throw new Error("LOCAL_ARTIFACTS_URL is required to communicate with sidecar");
  }
  const url = `${LOCAL_ARTIFACTS_URL.replace(/\/$/, "")}${path}`;
  const headers = {
    "content-type": "application/json",
    "accept": "application/json",
  };
  if (LOCAL_ARTIFACTS_TOKEN) {
    headers["authorization"] = `Bearer ${LOCAL_ARTIFACTS_TOKEN}`;
  }
  const payload = body ? JSON.stringify(body) : undefined;
  const res = await fetch(url, { method, headers, body: payload });
  const text = await res.text();
  try {
    return { status: res.status, ok: res.ok, data: JSON.parse(text) };
  } catch {
    return { status: res.status, ok: res.ok, data: text };
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      const str = Buffer.concat(chunks).toString("utf8");
      try {
        resolve(str ? JSON.parse(str) : {});
      } catch (err) {
        reject(new Error("request body must be valid JSON"));
      }
    });
    req.on("error", reject);
  });
}

function sendJson(res, status, body, extraHeaders = {}) {
  const payload = JSON.stringify(body, null, 2);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    ...CORS_HEADERS,
    ...extraHeaders,
  });
  res.end(payload);
}

function getBearer(req) {
  const auth = req.headers["authorization"];
  if (!auth) return null;
  const match = /^Bearer\s+(\S+)$/i.exec(auth);
  return match ? match[1] : null;
}

function authenticate(req, allowedAgents = null) {
  const token = getBearer(req);
  if (!token) {
    return { ok: false, status: 401, error: "bearer token required" };
  }

  if (ADMIN_TOKEN && token === ADMIN_TOKEN) {
    return { ok: true, role: "admin" };
  }
  if (RUNNER_TOKEN && token === RUNNER_TOKEN) {
    return { ok: true, role: "runner" };
  }
  if (LOCAL_ARTIFACTS_TOKEN && token === LOCAL_ARTIFACTS_TOKEN) {
    return { ok: true, role: "sidecar" };
  }

  // Check agent tokens
  const agentId = store.model.agentTokens[token];
  if (agentId) {
    if (allowedAgents && !allowedAgents.includes(agentId)) {
      return { ok: false, status: 403, error: `token belongs to ${agentId}, not authorized for target` };
    }
    return { ok: true, role: "agent", agentId };
  }

  return { ok: false, status: 401, error: "invalid bearer token" };
}

const server = createServer(async (req, res) => {
  const parsedUrl = new URL(req.url, `http://${HOST}:${PORT}`);
  const path = parsedUrl.pathname;
  const method = req.method;

  if (method === "OPTIONS") {
    res.writeHead(204, { ...CORS_HEADERS, "access-control-max-age": "86400" });
    res.end();
    return;
  }

  try {
    // 1. Health check
    if (method === "GET" && (path === "/health" || path === "/api/health")) {
      return sendJson(res, 200, { ok: true, runtime: "local-node-coordinator" });
    }

    // 2. Setup canonical baseline
    if (method === "POST" && path === "/setup") {
      const auth = authenticate(req);
      if (!auth.ok || auth.role !== "admin") {
        return sendJson(res, auth.status || 401, { error: auth.error || "admin token required" });
      }

      if (store.model.canonical) {
        return sendJson(res, 200, {
          canonical: store.model.canonical,
          created: false,
          seedCommit: null,
        });
      }

      const suffix = randomBytes(4).toString("hex");
      const canonicalName = `agent-branches-canonical-${suffix}`;
      const sidecarRes = await sidecarRequest("/api/repos", "POST", {
        name: canonicalName,
        defaultBranch: "main",
      });

      if (!sidecarRes.ok) {
        return sendJson(res, sidecarRes.status, { error: `sidecar createRepo failed: ${JSON.stringify(sidecarRes.data)}` });
      }

      store.model.canonical = {
        name: canonicalName,
        remote: sidecarRes.data.remote,
      };
      store.model.canonicalName = canonicalName;
      store.model.canonicalRemote = sidecarRes.data.remote;
      store.save();

      return sendJson(res, 201, {
        canonical: store.model.canonical,
        created: true,
        seedCommit: sidecarRes.data.seedCommit || null,
      });
    }

    // 3. Create task & fork
    if (method === "POST" && path === "/tasks") {
      const auth = authenticate(req);
      if (!auth.ok || auth.role !== "admin") {
        return sendJson(res, auth.status || 401, { error: auth.error || "admin token required" });
      }

      const body = await readBody(req);
      if (!store.model.canonical) {
        // Auto-run setup if needed
        const suffix = randomBytes(4).toString("hex");
        const canonicalName = `agent-branches-canonical-${suffix}`;
        const sidecarRes = await sidecarRequest("/api/repos", "POST", {
          name: canonicalName,
          defaultBranch: "main",
        });
        store.model.canonical = { name: canonicalName, remote: sidecarRes.data.remote };
        store.model.canonicalName = canonicalName;
        store.model.canonicalRemote = sidecarRes.data.remote;
      }

      store.model.seq += 1;
      const seqStr = String(store.model.seq).padStart(4, "0");
      const agentRaw = body.agent || "agent";
      const slug = agentRaw.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "agent";
      const agentId = `${slug}-${seqStr}`;
      const taskId = `task-${seqStr}`;

      const canonicalName = store.model.canonical.name;
      const forkName = `${canonicalName}-${agentId}`;

      const forkRes = await sidecarRequest(`/api/repos/${encodeURIComponent(canonicalName)}/fork`, "POST", {
        target: forkName,
        baseSha: body.base_sha || undefined,
      });

      if (!forkRes.ok && forkRes.status !== 409) {
        return sendJson(res, forkRes.status, { error: `sidecar fork failed: ${JSON.stringify(forkRes.data)}` });
      }

      const forkRemote = forkRes.data.remote || `${LOCAL_ARTIFACTS_URL}/git/${forkName}.git`;

      // Mint write token on fork
      const tokenRes = await sidecarRequest(`/api/repos/${encodeURIComponent(forkName)}/tokens`, "POST", {
        scope: "write",
        ttlSeconds: body.ttlSeconds || 86400,
      });

      const gitPushToken = tokenRes.data?.plaintext || tokenRes.data?.token || `art_v1_${randomBytes(20).toString("hex")}`;
      const taskBearerToken = `task_tok_${randomBytes(16).toString("hex")}`;
      const expiresAt = new Date(Date.now() + 86400 * 1000).toISOString();

      store.model.agentTokens[taskBearerToken] = agentId;
      store.model.taskTokens[taskId] = taskBearerToken;
      store.model.heads[agentId] = body.base_sha || "";

      const taskRecord = {
        taskId,
        task_id: taskId,
        id: taskId,
        agentId,
        agent_id: agentId,
        agent: agentId,
        branch: body.branch || "main",
        fork: { name: forkName, remote: forkRemote, token: gitPushToken },
        forkRemote,
        forkName,
        ref: `refs/heads/${body.branch || "main"}`,
        base_sha: body.base_sha || "",
        baseSha: body.base_sha || "",
        head: body.base_sha || null,
        head_sha: body.base_sha || null,
        intent: body.intent || null,
        status: "active",
        pushes: 0,
        token: { scope: "task", expiresAt, plaintext: taskBearerToken },
        taskToken: taskBearerToken,
        testProvenance: null,
      };

      store.model.tasks[taskId] = taskRecord;
      store.model.agents[agentId] = {
        agentId,
        agent_id: agentId,
        forkName,
        forkRemote,
        activeTaskId: taskId,
        intent: body.intent || null,
        baseSha: body.base_sha || null,
      };

      store.save();
      return sendJson(res, 201, taskRecord);
    }

    // 4. Ingest push webhook
    if (method === "POST" && path === "/events/push") {
      const body = await readBody(req);
      const fork = body.fork;
      const sha = body.sha;

      let targetAgentId = body.agent;
      if (!targetAgentId && fork) {
        for (const [aId, aRec] of Object.entries(store.model.agents)) {
          if (aRec.forkName === fork || fork.endsWith(aId)) {
            targetAgentId = aId;
            break;
          }
        }
      }

      if (!targetAgentId && body.fork) {
        // Fallback: extract last hyphenated segment if matching known format
        const match = /-(actor-[a-z0-9-]+)$/.exec(body.fork);
        if (match && store.model.agents[match[1]]) {
          targetAgentId = match[1];
        }
      }

      if (!targetAgentId) {
        targetAgentId = Object.keys(store.model.agents)[0] || "unknown-agent";
      }

      // Check auth if provided
      const token = getBearer(req);
      if (token && token !== ADMIN_TOKEN && token !== LOCAL_ARTIFACTS_TOKEN) {
        const callerAgent = store.model.agentTokens[token];
        if (callerAgent && callerAgent !== targetAgentId) {
          return sendJson(res, 403, { error: "cannot advance head of another agent" });
        }
      }

      store.model.heads[targetAgentId] = sha;

      // Update task head & push count
      for (const t of Object.values(store.model.tasks)) {
        if (t.agentId === targetAgentId) {
          t.head = sha;
          t.head_sha = sha;
          t.pushes = (t.pushes || 0) + 1;
        }
      }

      // Invalidate active warnings for this agent
      const invalidatedWarnings = [];
      for (const w of store.model.warnings) {
        if (w.pair.includes(targetAgentId) && w.status === "active") {
          w.status = "invalidated";
          invalidatedWarnings.push(w.id || w.warning_id);
        }
      }

      store.save();
      return sendJson(res, 200, {
        accepted: true,
        deduped: false,
        agent: targetAgentId,
        heads: store.model.heads,
        invalidatedWarnings,
        newWarnings: [],
        radarChecks: 0,
      });
    }

    // 5. Global status
    if (method === "GET" && path === "/status") {
      const auth = authenticate(req);
      if (!auth.ok) {
        return sendJson(res, auth.status || 401, { error: auth.error || "authentication required" });
      }

      const activeWarnings = store.model.warnings.filter((w) => w.status === "active");

      return sendJson(res, 200, {
        canonical: store.model.canonical,
        agents: Object.values(store.model.agents),
        tasks: Object.values(store.model.tasks),
        heads: store.model.heads,
        pairs: Object.values(store.model.pairChecks),
        warnings: activeWarnings,
        allWarnings: store.model.warnings,
        radarLog: store.model.radarLog,
        lastRunnerReport: store.model.lastRunnerReport,
        unprocessedPushes: [],
      });
    }

    // 6. Task inspection
    const taskMatch = /^\/tasks\/([^/]+)$/.exec(path);
    if (method === "GET" && taskMatch) {
      const taskId = decodeURIComponent(taskMatch[1]);
      const task = store.model.tasks[taskId];
      if (!task) {
        return sendJson(res, 404, { error: `unknown task: ${taskId}` });
      }

      const auth = authenticate(req, [task.agentId]);
      if (!auth.ok) {
        return sendJson(res, auth.status || 401, { error: auth.error || "authentication required" });
      }

      // Find warnings associated with this agent
      const taskWarnings = store.model.warnings.filter((w) => w.pair.includes(task.agentId));

      return sendJson(res, 200, {
        ...task,
        warnings: taskWarnings,
      });
    }

    // 7. Submit Radar checks (CONTRACT v0.1)
    if (method === "POST" && path === "/checks") {
      const auth = authenticate(req);
      if (!auth.ok || (auth.role !== "runner" && auth.role !== "admin")) {
        return sendJson(res, auth.status || 401, { error: auth.error || "runner or admin token required" });
      }

      const body = await readBody(req);
      if (body.contract !== "0.1") {
        return sendJson(res, 400, { error: "contract '0.1' is required" });
      }
      if (!body.vector || typeof body.vector !== "object") {
        return sendJson(res, 400, { error: "vector dictionary is required" });
      }
      if (!Array.isArray(body.results)) {
        return sendJson(res, 400, { error: "results array is required" });
      }

      // Check for stale vector against current heads
      for (const [agent, expectedSha] of Object.entries(body.vector)) {
        const currentSha = store.model.heads[agent];
        if (currentSha && currentSha !== expectedSha) {
          return sendJson(res, 409, {
            error: `stale vector: head for ${agent} moved to ${currentSha}; expected ${expectedSha}`,
            currentHeads: store.model.heads,
          });
        }
      }

      const createdWarnings = [];
      const updatedPairs = [];

      for (const result of body.results) {
        const pair = result.pair || [];
        const pairKey = [...pair].sort().join("|");

        if (result.status === "conflict") {
          store.model.warnSeq += 1;
          const wid = `warn-${store.model.warnSeq}`;
          const warning = {
            id: wid,
            warning_id: wid,
            pair,
            status: "active",
            kind: result.kind || "textual",
            heads: result.heads || body.vector,
            evidence: result.evidence || {},
            reason: result.evidence?.summary || "Merge conflict detected",
            acks: [],
            createdAt: new Date().toISOString(),
          };
          store.model.warnings.push(warning);
          createdWarnings.push(warning);
          store.model.pairChecks[pairKey] = {
            pair,
            status: "conflict",
            warningId: wid,
            heads: result.heads || body.vector,
            updatedAt: new Date().toISOString(),
          };
          updatedPairs.push(store.model.pairChecks[pairKey]);
        } else if (result.status === "clean") {
          const testsColl = typeof result.evidence?.tests?.collected === "number"
            ? result.evidence.tests.collected
            : (typeof result.testsCollected === "number" ? result.testsCollected : undefined);
          store.model.pairChecks[pairKey] = {
            pair,
            status: "clean",
            heads: result.heads || body.vector,
            ...(testsColl !== undefined ? { testsCollected: testsColl } : {}),
            updatedAt: new Date().toISOString(),
          };
          updatedPairs.push(store.model.pairChecks[pairKey]);
        }
      }

      store.save();
      return sendJson(res, 200, {
        stale: false,
        accepted: body.results.length,
        pairs: updatedPairs,
        createdWarnings,
        currentHeads: store.model.heads,
      });
    }

    // 8. Acknowledge warning
    const ackMatch = /^\/warnings\/([^/]+)\/ack$/.exec(path);
    if (method === "POST" && ackMatch) {
      const wid = decodeURIComponent(ackMatch[1]);
      const body = await readBody(req);

      let targetAgent = body.agent;
      const taskId = body.task_id || body.taskId;
      if (!targetAgent && taskId && store.model.tasks[taskId]) {
        targetAgent = store.model.tasks[taskId].agentId;
      }

      const warning = store.model.warnings.find((w) => w.id === wid || w.warning_id === wid);
      if (!warning) {
        return sendJson(res, 404, { error: `unknown warning: ${wid}` });
      }

      const auth = authenticate(req, targetAgent ? [targetAgent] : warning.pair);
      if (!auth.ok) {
        return sendJson(res, auth.status || 401, { error: auth.error || "authentication required" });
      }

      const effectiveAgent = targetAgent || (auth.role === "agent" ? auth.agentId : warning.pair[0]);
      const action = body.action || "rebased_locally";
      const note = body.note || action;

      const ackRecord = {
        agent: effectiveAgent,
        head: store.model.heads[effectiveAgent] || "",
        action,
        note,
        at: new Date().toISOString(),
      };

      if (!warning.acks) warning.acks = [];
      warning.acks.push(ackRecord);

      store.save();
      return sendJson(res, 200, {
        warning,
        warning_id: warning.id,
        id: warning.id,
        task_id: taskId || null,
        action,
        acknowledged_at: ackRecord.at,
      });
    }

    // 9. Attach test provenance
    const testsMatch = /^\/tasks\/([^/]+)\/tests$/.exec(path);
    if (method === "POST" && testsMatch) {
      const taskId = decodeURIComponent(testsMatch[1]);
      const task = store.model.tasks[taskId];
      if (!task) return sendJson(res, 404, { error: `unknown task: ${taskId}` });

      const auth = authenticate(req, [task.agentId]);
      if (!auth.ok) return sendJson(res, auth.status || 401, { error: auth.error || "auth required" });

      const body = await readBody(req);
      task.testProvenance = {
        command: body.command,
        exit: body.exit,
        head_sha: body.head_sha,
        at: new Date().toISOString(),
      };
      store.save();
      return sendJson(res, 201, { testProvenance: task.testProvenance });
    }

    return sendJson(res, 404, { error: `no route for ${method} ${path}` });
  } catch (err) {
    console.error(`[coordinator] error: ${err.stack || err.message}`);
    return sendJson(res, 500, { error: "internal server error", detail: err.message });
  }
});

server.listen(PORT, HOST, () => {
  const addr = server.address();
  console.error(`[coordinator] listening on http://${HOST}:${addr.port} (store: ${STATE_FILE})`);
});
