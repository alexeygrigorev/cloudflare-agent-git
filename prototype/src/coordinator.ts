import { DurableObject } from "cloudflare:workers";
import { LocalArtifacts } from "./artifacts/local.js";
import { RealArtifacts } from "./artifacts/real.js";
import { SidecarArtifacts } from "./artifacts/sidecar.js";
import { radarFromEnv, type Radar } from "./radar.js";
import type { ArtifactsPort } from "./types.js";

export interface AgentRecord {
  agentId: string;
  taskId: string;
  forkName: string;
  forkRemote: string;
  ref: string;
  head: string | null;
  pushes: number;
  createdAt: string;
  lastPushAt: string | null;
}

export interface TaskRecord {
  taskId: string;
  agentId: string;
  forkName: string;
  forkRemote: string;
  ref: string;
  createdAt: string;
}

export interface WarningRecord {
  id: string;
  pair: [string, string];
  headsAtIssue: { a: string; b: string };
  reason: string;
  status: "active" | "invalidated";
  createdAt: string;
  invalidatedAt: string | null;
}

export interface RadarLogEntry {
  at: string;
  pair: [string, string];
  heads: { a: string; b: string };
  reason: string | null;
}

interface CheckResultPayload {
  pair: string[];
  heads: Record<string, string>;
  status: string;
  kind: string | null;
  evidence?: unknown;
}

interface CoordinatorModel {
  canonicalName: string | null;
  canonicalRemote: string | null;
  seq: number;
  agents: Record<string, AgentRecord>;
  tasks: Record<string, TaskRecord>;
  heads: Record<string, string>;
  seenPushes: string[];
  warnings: WarningRecord[];
  radarLog: RadarLogEntry[];
  lastChecks: { receivedAt: string; vector: Record<string, string>; results: number } | null;
}

function emptyModel(): CoordinatorModel {
  return {
    canonicalName: null,
    canonicalRemote: null,
    seq: 0,
    agents: {},
    tasks: {},
    heads: {},
    seenPushes: [],
    warnings: [],
    radarLog: [],
    lastChecks: null,
  };
}

const CANONICAL_BASE = "agent-branches-canonical";
const RADAR_LOG_CAP = 50;
const WARNINGS_CAP = 200;

export class Coordinator extends DurableObject {
  private readonly state: DurableObjectState;
  private readonly radar: Radar;
  private readonly localArtifacts = new LocalArtifacts("agent-branches-local");
  private model: CoordinatorModel | null = null;

  constructor(state: DurableObjectState, env: Env) {
    super(state, env);
    this.state = state;
    this.radar = radarFromEnv(env.RADAR_IMPL);
  }

  private async load(): Promise<CoordinatorModel> {
    if (this.model) {
      return this.model;
    }
    const stored = (await this.state.storage.get("model")) as CoordinatorModel | undefined;
    this.model = stored ?? emptyModel();
    return this.model;
  }

  private async persist(): Promise<void> {
    await this.state.storage.put("model", this.model);
  }

  private port(): ArtifactsPort {
    if (this.env.ARTIFACTS_IMPL === "sidecar" && this.env.SIDECAR_URL) {
      return new SidecarArtifacts(this.env.SIDECAR_URL, this.env.SIDECAR_TOKEN ?? "");
    }
    if (this.env.ARTIFACTS) {
      return new RealArtifacts(this.env.ARTIFACTS);
    }
    return this.localArtifacts;
  }

  async setup(): Promise<{
    canonical: { name: string; remote: string };
    created: boolean;
    seedCommit: string | null;
  }> {
    const model = await this.load();
    if (model.canonicalName) {
      return {
        canonical: { name: model.canonicalName, remote: model.canonicalRemote ?? "" },
        created: false,
        seedCommit: null,
      };
    }
    const port = this.port();
    const created = await port.createRepo(CANONICAL_BASE, {
      description: "Agent Branches canonical baseline",
      setDefaultBranch: "main",
    });
    const seed = await this.localSeedIfAvailable(port, CANONICAL_BASE);
    model.canonicalName = created.name;
    model.canonicalRemote = created.remote;
    await this.persist();
    return {
      canonical: { name: created.name, remote: created.remote },
      created: true,
      seedCommit: seed,
    };
  }

  private async localSeedIfAvailable(
    port: ArtifactsPort,
    repo: string,
  ): Promise<string | null> {
    if (port instanceof LocalArtifacts) {
      const commit = await port.applyPush(repo, "refs/heads/main", {
        message: "chore: seed canonical baseline",
      });
      return commit.id;
    }
    return null;
  }

  async createTask(input: { agent?: string; ttlSeconds?: number }): Promise<{
    taskId: string;
    agentId: string;
    fork: { name: string; remote: string };
    ref: string;
    token: { scope: string; expiresAt: string; plaintext: string };
    head: string | null;
  }> {
    const model = await this.load();
    if (!model.canonicalName) {
      await this.setup();
    }
    const canonical = model.canonicalName!;
    const port = this.port();
    model.seq += 1;
    const seq = String(model.seq).padStart(4, "0");
    const slug = (input.agent ?? "agent")
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "agent";
    const agentId = `${slug}-${seq}`;
    const taskId = `task-${seq}`;
    const forkName = `${canonical}-${agentId}`;
    const fork = await port.fork(canonical, forkName, {
      description: `Agent Branches fork for ${agentId}`,
      defaultBranchOnly: true,
    });
    const token = await port.mintToken(forkName, "write", input.ttlSeconds ?? 3600);
    const forkLog = await port.log(forkName, { limit: 1 });
    const head = forkLog[0]?.id ?? null;
    const ref = "refs/heads/main";
    const now = new Date().toISOString();
    model.agents[agentId] = {
      agentId,
      taskId,
      forkName,
      forkRemote: fork.remote,
      ref,
      head,
      pushes: 0,
      createdAt: now,
      lastPushAt: null,
    };
    model.tasks[taskId] = {
      taskId,
      agentId,
      forkName,
      forkRemote: fork.remote,
      ref,
      createdAt: now,
    };
    if (head) {
      const before = model.heads[agentId] ?? null;
      model.heads[agentId] = head;
      this.runRadar(model, { agent: agentId, ref, sha: head, before });
    }
    await this.persist();
    return {
      taskId,
      agentId,
      fork: { name: forkName, remote: fork.remote },
      ref,
      token: { scope: token.scope, expiresAt: token.expiresAt, plaintext: token.plaintext },
      head,
    };
  }

  async recordPush(input: {
    agent: string;
    fork?: string;
    ref?: string;
    sha: string;
  }): Promise<{
    accepted: boolean;
    deduped: boolean;
    heads: Record<string, string>;
    invalidatedWarnings: string[];
    newWarnings: WarningRecord[];
    radarChecks: number;
  }> {
    const model = await this.load();
    const agent = model.agents[input.agent];
    if (!agent) {
      throw new Error(`unknown agent: ${input.agent}`);
    }
    if (input.fork && input.fork !== agent.forkName && input.fork !== agent.forkRemote) {
      throw new Error(`fork ${input.fork} does not belong to agent ${input.agent}`);
    }
    const dedupKey = `${input.agent}:${input.sha}`;
    const deduped = model.seenPushes.includes(dedupKey) || model.heads[input.agent] === input.sha;
    if (deduped) {
      return {
        accepted: true,
        deduped: true,
        heads: model.heads,
        invalidatedWarnings: [],
        newWarnings: [],
        radarChecks: 0,
      };
    }
    const port = this.port();
    const known = await port.hasCommit(agent.forkName, input.sha);
    if (!known) {
      throw new Error(`commit ${input.sha} not found in ${agent.forkName}`);
    }
    const before = model.heads[input.agent] ?? null;
    const ref = input.ref ?? agent.ref;
    const now = new Date().toISOString();
    model.seenPushes.push(dedupKey);
    model.heads[input.agent] = input.sha;
    agent.head = input.sha;
    agent.pushes += 1;
    agent.lastPushAt = now;
    agent.ref = ref;
    const invalidatedWarnings = this.invalidateWarningsFor(model, input.agent, now);
    const radarOutcome = this.runRadar(model, { agent: input.agent, ref, sha: input.sha, before });
    const newWarnings = radarOutcome.created;
    await this.persist();
    return {
      accepted: true,
      deduped: false,
      heads: model.heads,
      invalidatedWarnings,
      newWarnings,
      radarChecks: radarOutcome.checks.length,
    };
  }

  async status(): Promise<{
    canonical: { name: string | null; remote: string | null };
    agents: AgentRecord[];
    heads: Record<string, string>;
    warnings: WarningRecord[];
    radarLog: RadarLogEntry[];
  }> {
    const model = await this.load();
    return {
      canonical: { name: model.canonicalName, remote: model.canonicalRemote },
      agents: Object.values(model.agents),
      heads: model.heads,
      warnings: [...model.warnings]
        .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
        .slice(0, 20),
      radarLog: [...model.radarLog].slice(-20).reverse(),
    };
  }

  async getTask(taskId: string): Promise<TaskRecord & { agent: AgentRecord | null }> {
    const model = await this.load();
    const task = model.tasks[taskId];
    if (!task) {
      throw new Error(`unknown task: ${taskId}`);
    }
    return { ...task, agent: model.agents[task.agentId] ?? null };
  }

  /**
   * Intake for external radar results (CONTRACT v0.1, as emitted by
   * `python3 -m radar ... --l1`). Rejects with stale:true (HTTP 409 at the
   * route) when any head in the payload vector no longer matches the current
   * head vector — a check against moved heads must not create warnings.
   */
  async submitChecks(payload: {
    contract?: string;
    vector?: Record<string, string>;
    results?: CheckResultPayload[];
  }): Promise<{
    accepted: boolean;
    stale: boolean;
    staleHeads: Record<string, { expected: string | null; got: string }>;
    warningsCreated: WarningRecord[];
    results: number;
  }> {
    const model = await this.load();
    if (payload.contract !== "0.1") {
      throw new Error("unsupported contract: expected 0.1");
    }
    const staleHeads: Record<string, { expected: string | null; got: string }> = {};
    for (const [agent, sha] of Object.entries(payload.vector ?? {})) {
      if (!model.agents[agent]) {
        throw new Error(`unknown agent: ${agent}`);
      }
      if (model.heads[agent] !== sha) {
        staleHeads[agent] = { expected: model.heads[agent] ?? null, got: sha };
      }
    }
    if (Object.keys(staleHeads).length > 0) {
      return { accepted: false, stale: true, staleHeads, warningsCreated: [], results: 0 };
    }
    const now = new Date().toISOString();
    const created: WarningRecord[] = [];
    let count = 0;
    for (const result of payload.results ?? []) {
      count += 1;
      const pair = [...result.pair].sort() as [string, string];
      const heads = {
        a: result.heads[pair[0]] ?? "",
        b: result.heads[pair[1]] ?? "",
      };
      const reason = result.status === "conflict" ? `radar-conflict:${result.kind ?? "unknown"}` : null;
      model.radarLog.push({ at: now, pair, heads, reason });
      if (reason) {
        const warning: WarningRecord = {
          id: `warn-${model.warnings.length + 1}`,
          pair,
          headsAtIssue: heads,
          reason,
          createdAt: now,
          invalidatedAt: null,
          status: "active",
        };
        model.warnings.push(warning);
        created.push(warning);
      }
    }
    if (model.radarLog.length > RADAR_LOG_CAP) {
      model.radarLog.splice(0, model.radarLog.length - RADAR_LOG_CAP);
    }
    if (model.warnings.length > WARNINGS_CAP) {
      model.warnings.splice(0, model.warnings.length - WARNINGS_CAP);
    }
    model.lastChecks = { receivedAt: now, vector: { ...(payload.vector ?? {}) }, results: count };
    await this.persist();
    return { accepted: true, stale: false, staleHeads: {}, warningsCreated: created, results: count };
  }

  async checksReceipt(): Promise<CoordinatorModel["lastChecks"]> {
    const model = await this.load();
    return model.lastChecks;
  }

  private invalidateWarningsFor(model: CoordinatorModel, agent: string, now: string): string[] {
    const invalidated: string[] = [];
    for (const warning of model.warnings) {
      if (warning.status === "active" && warning.pair.includes(agent)) {
        warning.status = "invalidated";
        warning.invalidatedAt = now;
        invalidated.push(warning.id);
      }
    }
    return invalidated;
  }

  private runRadar(
    model: CoordinatorModel,
    change: { agent: string; ref: string; sha: string; before: string | null },
  ): { checks: { pair: [string, string]; heads: { a: string; b: string } }[]; created: WarningRecord[] } {
    const siblings = Object.keys(model.heads);
    const checks = this.radar.onPush(change, model.heads, siblings);
    const now = new Date().toISOString();
    const created: WarningRecord[] = [];
    for (const check of checks) {
      const entry: RadarLogEntry = { at: now, pair: check.pair, heads: check.heads, reason: check.reason };
      model.radarLog.push(entry);
      if (model.radarLog.length > RADAR_LOG_CAP) {
        model.radarLog.splice(0, model.radarLog.length - RADAR_LOG_CAP);
      }
      if (check.reason) {
        const warning: WarningRecord = {
          id: `warn-${model.warnings.length + 1}`,
          pair: check.pair,
          headsAtIssue: check.heads,
          reason: check.reason,
          createdAt: now,
          invalidatedAt: null,
          status: "active",
        };
        model.warnings.push(warning);
        created.push(warning);
        if (model.warnings.length > WARNINGS_CAP) {
          model.warnings.splice(0, model.warnings.length - WARNINGS_CAP);
        }
      }
    }
    return { checks, created };
  }
}
