import { execSync, spawn } from "child_process";
import { resolve, join } from "path";
import { mkdirSync, rmSync, writeFileSync } from "fs";

const root = resolve(".local/tmp/harness-" + Date.now());
const childProcs = [];
const commandsRun = [];

function cleanup() {
  for (const child of childProcs) {
    if (!child.killed && child.pid) {
      try { process.kill(child.pid, "SIGKILL"); } catch (e) {}
    }
  }
  try { rmSync(root, { recursive: true, force: true }); } catch (e) {}
}

process.on("SIGINT", () => { cleanup(); process.exit(1); });
process.on("SIGTERM", () => { cleanup(); process.exit(1); });
process.on("uncaughtException", (err) => { console.error(err); cleanup(); process.exit(1); });

const globalTimeout = setTimeout(() => {
  console.error("Global timeout reached");
  cleanup();
  process.exit(1);
}, 60000);

function runGitSync(args, dir, token) {
  const env = { ...process.env };
  if (token) {
    env.GIT_CONFIG_COUNT = "1";
    env.GIT_CONFIG_KEY_0 = "http.extraHeader";
    env.GIT_CONFIG_VALUE_0 = `Authorization: Bearer ${token}`;
  }
  const cmd = `git ${args.join(" ")}`;
  try {
    execSync(cmd, { cwd: dir, env, stdio: "ignore" });
    commandsRun.push({ command: cmd, exit: 0 });
  } catch (e) {
    commandsRun.push({ command: cmd, exit: e.status || 1 });
    throw e;
  }
}

function runGitAsync(args, dir, token, name) {
  return new Promise((res) => {
    const env = { ...process.env };
    if (token) {
      env.GIT_CONFIG_COUNT = "1";
      env.GIT_CONFIG_KEY_0 = "http.extraHeader";
      env.GIT_CONFIG_VALUE_0 = `Authorization: Bearer ${token}`;
    }
    const cmdStr = `git ${args.join(" ")}`;
    const s = Date.now();
    const child = spawn("git", args, { cwd: dir, env, stdio: "ignore" });
    childProcs.push(child);
    child.on("close", (code) => {
      const e = Date.now();
      commandsRun.push({ command: cmdStr, exit: code });
      res({ name, s, e, code });
    });
  });
}

async function main() {
  rmSync(root, { recursive: true, force: true });
  mkdirSync(root, { recursive: true });

  const pSidecar = 8790 + Math.floor(Math.random() * 100);
  const pCoord = pSidecar + 100;
  const sharedToken = "shared-" + Date.now();
  const adminToken = "admin-" + Date.now();
  const runnerToken = "runner-" + Date.now();

  const sidecarProcess = spawn("node", ["prototype/local-artifacts/sidecar.mjs"], {
    env: { ...process.env, SIDECAR_PORT: pSidecar, SIDECAR_TOKEN: sharedToken, SIDECAR_NOTIFY_URL: `http://127.0.0.1:${pCoord}/events/push`, SIDECAR_ROOT: join(root, "sidecar") },
    stdio: ["ignore", "pipe", "pipe"]
  });
  childProcs.push(sidecarProcess);
  
  await new Promise(res => {
    sidecarProcess.stderr.on("data", d => {
      if (d.toString().includes("listening on")) res();
    });
  });

  const coordProcess = spawn("node", ["prototype/.build/node/src/local/main.js"], {
    env: { ...process.env, PORT: pCoord, LOCAL_ARTIFACTS_URL: `http://127.0.0.1:${pSidecar}`, LOCAL_ARTIFACTS_TOKEN: sharedToken, ADMIN_TOKEN: adminToken, RUNNER_TOKEN: runnerToken, COORDINATOR_STATE_FILE: join(root, "coord.json") },
    stdio: ["ignore", "pipe", "pipe"]
  });
  childProcs.push(coordProcess);
  
  await new Promise(res => {
    coordProcess.stderr.on("data", d => {
      if (d.toString().includes("listening on")) res();
    });
  });

  const postAuth = async (path, body, token) => {
    const res = await fetch(`http://127.0.0.1:${pCoord}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json", ...(token ? { "authorization": `Bearer ${token}` } : {}) },
      body: JSON.stringify(body)
    });
    return { status: res.status, ok: res.ok, body: await res.json().catch(()=>null) };
  };
  
  const getAuth = async (path, token) => {
    const headers = {};
    if (token) headers.authorization = `Bearer ${token}`;
    const res = await fetch(`http://127.0.0.1:${pCoord}${path}`, { headers });
    return { status: res.status, ok: res.ok, body: await res.json().catch(()=>null) };
  };

  try {
    // 5. Extended Auth Negatives
    const unauthStatus = await getAuth("/status", null);
    if (unauthStatus.status !== 401) throw new Error(`Expected 401, got ${unauthStatus.status}`);

    const resA = await postAuth("/tasks", { agent: "agent-a" }, adminToken);
    const resB = await postAuth("/tasks", { agent: "agent-b" }, adminToken);
    const resC = await postAuth("/tasks", { agent: "agent-c" }, adminToken);
    
    // 5. Extended Auth Negatives: anonymous GET /tasks/:id -> 401
    const taskUnauth = await getAuth(`/tasks/${resA.body.taskId}`, null);
    if (taskUnauth.status !== 401) throw new Error("Expected 401 on anonymous GET /tasks/:id");

    const cloneUrlA = `http://127.0.0.1:${pSidecar}/git/${resA.body.fork.name}.git`;
    const cloneUrlB = `http://127.0.0.1:${pSidecar}/git/${resB.body.fork.name}.git`;
    const cloneUrlC = `http://127.0.0.1:${pSidecar}/git/${resC.body.fork.name}.git`;

    const dirA = join(root, "a");
    const dirB = join(root, "b");
    const dirC = join(root, "c");
    
    // 1. Token Redaction: tokens in env, clean URLs
    runGitSync(["clone", cloneUrlA, dirA], root, resA.body.token.plaintext);
    runGitSync(["clone", cloneUrlB, dirB], root, resB.body.token.plaintext);
    runGitSync(["clone", cloneUrlC, dirC], root, resC.body.token.plaintext);

    runGitSync(["config", "user.name", "A"], dirA);
    runGitSync(["config", "user.email", "a@a"], dirA);
    execSync(`echo "A" > file.txt`, { cwd: dirA });
    runGitSync(["add", "file.txt"], dirA);
    runGitSync(["commit", "-m", "A"], dirA);

    runGitSync(["config", "user.name", "B"], dirB);
    runGitSync(["config", "user.email", "b@b"], dirB);
    execSync(`echo "B" > file.txt`, { cwd: dirB });
    runGitSync(["add", "file.txt"], dirB);
    runGitSync(["commit", "-m", "B"], dirB);

    runGitSync(["config", "user.name", "C"], dirC);
    runGitSync(["config", "user.email", "c@c"], dirC);
    execSync(`echo "C" > other.txt`, { cwd: dirC });
    runGitSync(["add", "other.txt"], dirC);
    runGitSync(["commit", "-m", "C"], dirC);

    // 2. Real Push Overlap & Timestamps
    const pushResults = await Promise.all([
      runGitAsync(["push", "origin", "main"], dirA, resA.body.token.plaintext, "A"),
      runGitAsync(["push", "origin", "main"], dirB, resB.body.token.plaintext, "B"),
      runGitAsync(["push", "origin", "main"], dirC, resC.body.token.plaintext, "C")
    ]);
    
    for (const r of pushResults) {
      if (r.code !== 0) throw new Error(`Push failed for ${r.name}`);
    }

    const minEnd = Math.min(...pushResults.map(r => r.e));
    const maxStart = Math.max(...pushResults.map(r => r.s));
    const overlap_ms = minEnd - maxStart;
    if (overlap_ms <= 0) throw new Error("Expected positive overlap for pushes");

    const timestamps = {};
    for (const r of pushResults) timestamps[r.name] = { start: r.s, end: r.e };

    const status1 = await getAuth("/status", adminToken);
    const heads = status1.body.heads;
    
    const runnerDir = join(root, "runner");
    mkdirSync(runnerDir);
    runGitSync(["init"], runnerDir);
    runGitSync(["fetch", cloneUrlA, "main:a"], runnerDir, resA.body.token.plaintext);
    runGitSync(["fetch", cloneUrlB, "main:b"], runnerDir, resB.body.token.plaintext);
    runGitSync(["fetch", cloneUrlC, "main:c"], runnerDir, resC.body.token.plaintext);

    let conflictAB = false;
    try { runGitSync(["merge-tree", "a", "b"], runnerDir); } catch (e) { conflictAB = e.status === 1; }
    if (!conflictAB) throw new Error("Expected A and B to conflict");
    
    let conflictAC = false;
    try { runGitSync(["merge-tree", "a", "c"], runnerDir); } catch (e) { conflictAC = e.status === 1; }
    if (conflictAC) throw new Error("Expected A and C to be clean");

    // 3. Full POST /checks Contract
    const checksRes = await postAuth("/checks", {
      contract: "0.1",
      vector: heads,
      policy: { merge: "git-merge-tree", tests: { command: null, budget_s: 15 } },
      coverage: { pairs_checked: 2, tests_collected: 0 },
      results: [
        {
          pair: [resA.body.agentId, resB.body.agentId].sort(),
          heads: { [resA.body.agentId]: heads[resA.body.agentId], [resB.body.agentId]: heads[resB.body.agentId] },
          status: "conflict",
          kind: "textual",
          evidence: { summary: "conflict in file.txt" }
        },
        {
          pair: [resA.body.agentId, resC.body.agentId].sort(),
          heads: { [resA.body.agentId]: heads[resA.body.agentId], [resC.body.agentId]: heads[resC.body.agentId] },
          status: "clean",
          kind: "textual",
          evidence: { summary: "clean disjoint edit" }
        }
      ]
    }, runnerToken);
    if (!checksRes.ok) throw new Error("POST /checks failed: " + JSON.stringify(checksRes.body));

    const status2 = await getAuth("/status", adminToken);
    const pairAB = status2.body.pairs.find(p => p.pair.includes(resA.body.agentId) && p.pair.includes(resB.body.agentId));
    if (pairAB.status !== "conflict") throw new Error("Expected conflict pair status");
    const pairAC = status2.body.pairs.find(p => p.pair.includes(resA.body.agentId) && p.pair.includes(resC.body.agentId));
    if (pairAC.status !== "clean") throw new Error("Expected clean pair status");
    
    if (status2.body.warnings.length !== 1) throw new Error("Expected 1 warning");
    
    const warningId = status2.body.warnings[0].id;
    const ackFail = await postAuth(`/warnings/${warningId}/ack`, { agent: resA.body.agentId }, resC.body.token.plaintext);
    if (ackFail.status !== 403) throw new Error("Expected 403 for wrong agent ACK, got " + ackFail.status);

    const ackOk = await postAuth(`/warnings/${warningId}/ack`, { agent: resA.body.agentId }, resA.body.token.plaintext);
    if (!ackOk.ok) throw new Error("Expected 200 for correct agent ACK");

    // 5. Extended Auth Negatives: 403 on foreign POST /tasks/:id/tests
    const testForeign = await postAuth(`/tasks/${resA.body.taskId}/tests`, { command: "test", exit: 0, head_sha: heads[resA.body.agentId] }, resB.body.token.plaintext);
    if (testForeign.status !== 403) throw new Error("Expected 403 on foreign POST /tasks/:id/tests");

    // 4. Safety Semantics: unknown never clean
    await postAuth("/checks", {
      contract: "0.1",
      vector: heads,
      policy: { merge: "git-merge-tree", tests: { command: null, budget_s: 15 } },
      coverage: { pairs_checked: 1, tests_collected: 0 },
      results: [
        {
          pair: [resB.body.agentId, resC.body.agentId].sort(),
          heads: { [resB.body.agentId]: heads[resB.body.agentId], [resC.body.agentId]: heads[resC.body.agentId] },
          status: "unknown",
          kind: "textual",
          evidence: { summary: "unknown" }
        }
      ]
    }, runnerToken);
    
    const statusUnknown = await getAuth("/status", adminToken);
    const pairBC = statusUnknown.body.pairs.find(p => p.pair.includes(resB.body.agentId) && p.pair.includes(resC.body.agentId));
    if (pairBC.status !== "unknown") throw new Error("Expected unknown pair status");

    // Push again and assert stale
    execSync(`echo "A2" > file.txt`, { cwd: dirA });
    runGitSync(["add", "file.txt"], dirA);
    runGitSync(["commit", "-m", "A2"], dirA);
    runGitSync(["push", "origin", "main"], dirA, resA.body.token.plaintext);

    const staleRes = await postAuth("/checks", {
      contract: "0.1",
      vector: heads, // old heads
      policy: { merge: "git-merge-tree", tests: { command: null, budget_s: 15 } },
      coverage: { pairs_checked: 1, tests_collected: 0 },
      results: [
        {
          pair: [resA.body.agentId, resB.body.agentId].sort(),
          heads: { [resA.body.agentId]: heads[resA.body.agentId], [resB.body.agentId]: heads[resB.body.agentId] },
          status: "conflict",
          kind: "textual",
          evidence: { summary: "conflict in file.txt" }
        }
      ]
    }, runnerToken);
    if (staleRes.status !== 409) throw new Error("Expected 409 for stale vector, got " + staleRes.status);
    
    const status3 = await getAuth("/status", adminToken);
    const newWarning = status3.body.warnings.find(w => w.id === warningId);
    if (newWarning && newWarning.status === "active") throw new Error("Warning should have been cleared by push");

    // 4. Safety Semantics: assert pair reverts to not_checked with stale: true upon member head advance
    const pairABStale = status3.body.pairs.find(p => p.pair.includes(resA.body.agentId) && p.pair.includes(resB.body.agentId));
    if (pairABStale.status !== "not_checked") throw new Error("Expected pair to revert to not_checked");
    if (pairABStale.stale !== true) throw new Error("Expected pair to be stale");

    const finalStatus = await getAuth("/status", adminToken);
    
    // 7. Comprehensive Output JSON & 8. Explicit Unresolved Limits
    const resultObj = {
      overlap_ms,
      timestamps,
      commands: commandsRun,
      topology: "scripted_local_process",
      run_instructions: "Run `node prototype/demo/concurrent.mjs` from the repository root.",
      unresolved_limits: ["genuine model-agent concurrency", "two-computer integration gates"],
      hashes: finalStatus.body.heads,
      testResults: "Success",
      nextStep: "Finished"
    };
    writeFileSync(resolve(".local", "result.json"), JSON.stringify(resultObj, null, 2));
    
  } finally {
    clearTimeout(globalTimeout);
    cleanup();
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
