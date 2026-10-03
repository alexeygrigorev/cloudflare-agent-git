import { DurableObject } from "cloudflare:workers";
import { RealArtifacts } from "./artifacts/real.js";
import { SidecarArtifacts } from "./artifacts/sidecar.js";
import { RADAR_STATUSES, pairKey, radarFromEnv, type Radar, type RadarPairResult, type RadarStatus } from "./radar.js";

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
  /** Canonical commit this task's fork was created from (codex C-1306). */
  baseSha: string;
  /** Free-form intent text supplied at task creation (codex C-1306). */
  intent: string | null;
  /** Last posted test provenance (codex C-1306); agents POST /tasks/:id/tests. */
  testProvenance: TestProvenance | null;
}

export interface TestProvenance {
  command: string;
  exit: number;
  head_sha: string;
  at: string;
}

export interface WarningAck {
  agent: string;
  /** Head of the acknowledging agent's fork at ack time (codex C-1306). */
  head: string | null;
  note?: string;
  at: string;
}

export interface WarningRecord {
  id: string;
  pair: [string, string];
  headsAtIssue: { a: string; b: string };
  reason: string;
  status: "active" | "invalidated";
  createdAt: string;
  invalidatedAt: string | null;
  /** Conflict classifier from the radar/runner result, when provided. */
  kind?: string;
  /** How the conflict was detected. */
  evidence?: string;
  /** Set when a later clean check at the same heads resolved the warning. */
  resolvedBy?: string;
  /** Acknowledgements recorded via POST /warnings/:id/ack. */
  acks: WarningAck[];
}

export interface RadarLogEntry {
  at: string;
  pair: [string, string];
  heads: { a: string; b: string };
  status: RadarStatus;
  kind?: string;
  evidence?: string;
}

/** Last accepted radar/runner result for a pair, at an exact pair vector. */
export interface PairCheckRecord {
  key: string;
  pair: [string, string];
  status: RadarStatus;
  kind?: string;
  evidence?: string;
  vector: { a: string; b: string };
  at: string;
}

/** Derived per-pair view for /status: fresh results only; stale => not_checked. */
export interface PairStatusView {
  pair: [string, string];
  heads: { a: string; b: string };
  status: RadarStatus;
  kind?: string;
  evidence?: string;
  checkedAt: string | null;
  /** True when a stored check exists but no longer matches the current heads. */
  stale: boolean;
  activeWarningIds: string[];
}

const CANONICAL_BASE = "agent-branches-canonical";
const RADAR_LOG_CAP = 50;
const WARNINGS_CAP = 200;

export interface RunnerReport {
  policy: string;
  coverage: string[];
  accepted: number;
  at: string;
  vector: Record<string, string>;
}

interface CoordinatorModel {
  canonicalName: string | null;
  canonicalRemote: string | null;
  seq: number;
  warnSeq: number;
  agents: Record<string, AgentRecord>;
  tasks: Record<string, TaskRecord>;
  heads: Record<string, string>;
  seenPushes: string[];
  warnings: WarningRecord[];
  radarLog: RadarLogEntry[];
  pairChecks: Record<string, PairCheckRecord>;
  lastRunnerReport: RunnerReport | null;
}

function emptyModel(): CoordinatorModel {
  return {
    canonicalName: null,
    canonicalRemote: null,
    seq: 0,
    warnSeq: 0,
    agents: {},
    tasks: {},
    heads: {},
    seenPushes: [],
    warnings: [],
    radarLog: [],
    pairChecks: {},
    lastRunnerReport: null,
  };
}

function randomSuffix(): string {
  const bytes = new Uint8Array(4);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export class Coordinator extends DurableObject {
  private readonly state: DurableObjectState;
  private readonly radar: Radar;
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
    // Migrate models persisted before a field existed.
    this.model.pairChecks ??= {};
    this.model.warnSeq ??= this.model.warnings.length;
    this.model.lastRunnerReport ??= null;
    return this.model;
  }

  private async persist(): Promise<void> {
    await this.state.storage.put("model", this.model);
  }

  /**
   * Deployment boundary (codex C-1309): the Worker/DO never runs git. It
   * talks to either the real Artifacts binding or the local Node sidecar.
   */
  private port(): RealArtifacts | SidecarArtifacts {
    if (this.env.ARTIFACTS) {
      return new RealArtifacts(this.env.ARTIFACTS);
    }
    if (this.env.LOCAL_ARTIFACTS_URL) {
      return new SidecarArtifacts(this.env.LOCAL_ARTIFACTS_URL, this.env.LOCAL_ARTIFACTS_TOKEN);
    }
    throw new Error(
      "no Artifacts backend configured: set the ARTIFACTS binding (real) or LOCAL_ARTIFACTS_URL (local sidecar)",
    );
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
    // Per-instance suffix so isolated storage (tests) never collides on the
    // sidecar's on-disk repo namespace.
    const name = `${CANONICAL_BASE}-${randomSuffix()}`;
    const created = await port.createRepo(name, {
      description: "Agent Branches canonical baseline",
      setDefaultBranch: "main",
    });
    const seed = await port.headCommit(created.name);
    model.canonicalName = created.name;
    model.canonicalRemote = created.remote;
    await this.persist();
    return {
      canonical: { name: created.name, remote: created.remote },
      created: true,
      seedCommit: seed,
    };
  }

  async createTask(input: {
    agent?: string;
    intent?: string;
    baseSha?: string;
    ttlSeconds?: number;
  }): Promise<{
    taskId: string;
    agentId: string;
    fork: { name: string; remote: string };
    ref: string;
    base_sha: string;
    intent: string | null;
    token: { scope: string; expiresAt: string; plaintext: string };
    head: string | null;
  }> {
    const model = await this.load();
    if (!model.canonicalName) {
      await this.setup();
    }
    const canonical = model.canonicalName!;
    const port = this.port();
    const canonicalHead = await port.headCommit(canonical);
    const baseSha = input.baseSha ?? canonicalHead ?? "";
    if (!/^[0-9a-f]{40}$/.test(baseSha)) {
      throw new Error(`base_sha must be a 40-hex commit id (got invalid value)`);
    }
    if (baseSha !== canonicalHead) {
      // Verify the requested base exists in the canonical first-parent
      // history (documented log op; capped at its max limit).
      const history = await port.log(canonical, { limit: 1000 });
      if (!history.some((commit) => commit.id === baseSha)) {
        throw new Error(`base_sha ${baseSha} not found in canonical history`);
      }
    }
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
      baseSha,
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
      baseSha,
      intent: input.intent ?? null,
      testProvenance: null,
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
      base_sha: baseSha,
      intent: input.intent ?? null,
      token: { scope: token.scope, expiresAt: token.expiresAt, plaintext: token.plaintext },
      head,
    };
  }

  async recordPush(input: {
    agent?: string;
    fork?: string;
    ref?: string;
    sha: string;
  }): Promise<{
    accepted: boolean;
    deduped: boolean;
    agent: string;
    heads: Record<string, string>;
    invalidatedWarnings: string[];
    newWarnings: WarningRecord[];
    radarChecks: number;
  }> {
    const model = await this.load();
    // The sidecar webhook posts {fork, ref, sha} without an agent id; resolve
    // the owning agent from the fork (codex C-1309 #7a).
    let agentRecord = input.agent ? model.agents[input.agent] : undefined;
    if (!agentRecord && input.fork) {
      agentRecord = Object.values(model.agents).find(
        (candidate) => candidate.forkName === input.fork || candidate.forkRemote === input.fork,
      );
    }
    if (!agentRecord) {
      throw new Error(`unknown agent: ${input.agent ?? input.fork}`);
    }
    const agentId = agentRecord.agentId;
    if (input.fork && input.fork !== agentRecord.forkName && input.fork !== agentRecord.forkRemote) {
      throw new Error(`fork ${input.fork} does not belong to agent ${agentId}`);
    }
    const dedupKey = `${agentId}:${input.sha}`;
    const deduped = model.seenPushes.includes(dedupKey) || model.heads[agentId] === input.sha;
    if (deduped) {
      return {
        accepted: true,
        deduped: true,
        agent: agentId,
        heads: model.heads,
        invalidatedWarnings: [],
        newWarnings: [],
        radarChecks: 0,
      };
    }
    const port = this.port();
    const known = await port.hasCommit(agentRecord.forkName, input.sha);
    if (!known) {
      throw new Error(`commit ${input.sha} not found in ${agentRecord.forkName}`);
    }
    const before = model.heads[agentId] ?? null;
    const ref = input.ref ?? agentRecord.ref;
    const now = new Date().toISOString();
    model.seenPushes.push(dedupKey);
    model.heads[agentId] = input.sha;
    agentRecord.head = input.sha;
    agentRecord.pushes += 1;
    agentRecord.lastPushAt = now;
    agentRecord.ref = ref;
    const invalidatedWarnings = this.invalidateWarningsFor(model, agentId, now);
    const radarOutcome = this.runRadar(model, { agent: agentId, ref, sha: input.sha, before });
    const newWarnings = radarOutcome.created;
    await this.persist();
    return {
      accepted: true,
      deduped: false,
      agent: agentId,
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
    pairs: PairStatusView[];
    warnings: WarningRecord[];
    radarLog: RadarLogEntry[];
    lastRunnerReport: RunnerReport | null;
  }> {
    const model = await this.load();
    return {
      canonical: { name: model.canonicalName, remote: model.canonicalRemote },
      agents: Object.values(model.agents),
      heads: model.heads,
      pairs: this.pairViews(model),
      warnings: [...model.warnings]
        .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
        .slice(0, 20),
      radarLog: [...model.radarLog].slice(-20).reverse(),
      lastRunnerReport: model.lastRunnerReport,
    };
  }

  async getTask(
    taskId: string,
  ): Promise<
    TaskRecord & {
      base_sha: string;
      agent: AgentRecord | null;
      head: string | null;
      pushes: number;
      warnings: WarningRecord[];
      testProvenance: TestProvenance | null;
    }
  > {
    const model = await this.load();
    const task = model.tasks[taskId];
    if (!task) {
      throw new Error(`unknown task: ${taskId}`);
    }
    const agent = model.agents[task.agentId] ?? null;
    const warnings = model.warnings
      .filter((warning) => warning.pair.includes(task.agentId))
      .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
    return {
      ...task,
      base_sha: task.baseSha,
      agent,
      head: agent?.head ?? null,
      pushes: agent?.pushes ?? 0,
      warnings,
      testProvenance: task.testProvenance,
    };
  }

  /** Record which agent acknowledged which warning at which head (C-1306). */
  async ackWarning(
    warningId: string,
    input: { agent: string; note?: string },
  ): Promise<{ warning: WarningRecord }> {
    const model = await this.load();
    if (!(input.agent in model.agents)) {
      throw new Error(`unknown agent: ${input.agent}`);
    }
    const warning = model.warnings.find((candidate) => candidate.id === warningId);
    if (!warning) {
      throw new Error(`unknown warning: ${warningId}`);
    }
    warning.acks ??= [];
    warning.acks.push({
      agent: input.agent,
      head: model.heads[input.agent] ?? null,
      note: input.note,
      at: new Date().toISOString(),
    });
    await this.persist();
    return { warning };
  }

  /** Attach test provenance to a task (C-1306): {command, exit, head_sha, at}. */
  async recordTestProvenance(
    taskId: string,
    input: { command: string; exit: number; head_sha: string },
  ): Promise<{ testProvenance: TestProvenance }> {
    const model = await this.load();
    const task = model.tasks[taskId];
    if (!task) {
      throw new Error(`unknown task: ${taskId}`);
    }
    if (typeof input.command !== "string" || input.command.length === 0) {
      throw new Error("test provenance requires a non-empty command");
    }
    if (!Number.isInteger(input.exit)) {
      throw new Error("test provenance requires an integer exit code");
    }
    if (!/^[0-9a-f]{40}$/.test(input.head_sha)) {
      throw new Error("test provenance requires a 40-hex head_sha");
    }
    const port = this.port();
    if (!(await port.hasCommit(task.forkName, input.head_sha))) {
      throw new Error(`commit ${input.head_sha} not found in ${task.forkName}`);
    }
    task.testProvenance = { command: input.command, exit: input.exit, head_sha: input.head_sha, at: new Date().toISOString() };
    await this.persist();
    return { testProvenance: task.testProvenance };
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

  /**
   * Trusted-runner submission endpoint (codex C-1309 #7b). The full head
   * vector must match the DO's current heads exactly; a stale vector is
   * rejected so results always refer to a well-defined state. Returns
   * `{stale: true}` (the route maps that to 409) instead of throwing, since
   * custom error properties do not survive RPC marshalling.
   */
  async submitChecks(input: {
    vector: Record<string, string>;
    policy: string;
    coverage?: string[];
    results: { pair: [string, string]; status: string; kind?: string; evidence?: string }[];
  }): Promise<
    | { stale: true; currentHeads: Record<string, string> }
    | {
        stale: false;
        accepted: number;
        pairs: PairStatusView[];
        createdWarnings: WarningRecord[];
        currentHeads: Record<string, string>;
        runnerReport: RunnerReport;
      }
  > {
    const model = await this.load();
    const currentKeys = Object.keys(model.heads).sort();
    const vectorKeys = Object.keys(input.vector ?? {}).sort();
    const stale =
      currentKeys.length !== vectorKeys.length ||
      currentKeys.some((key, index) => key !== vectorKeys[index] || model.heads[key] !== input.vector[key]);
    if (stale) {
      return { stale: true, currentHeads: model.heads };
    }
    const applied = await this.applyCheckResults({ policy: input.policy, results: input.results });
    const model2 = await this.load();
    const runnerReport: RunnerReport = {
      policy: input.policy,
      coverage: input.coverage ?? [],
      accepted: applied.accepted,
      at: new Date().toISOString(),
      vector: { ...input.vector },
    };
    model2.lastRunnerReport = runnerReport;
    await this.persist();
    return {
      stale: false,
      accepted: applied.accepted,
      pairs: applied.pairs,
      createdWarnings: applied.createdWarnings,
      currentHeads: model2.heads,
      runnerReport,
    };
  }

  /**
   * Apply trusted radar/runner results (from POST /checks or direct calls).
   * Each result is stored per pair at its exact pair vector; only
   * `status: "conflict"` creates warnings; a later `clean` result at the same
   * vector resolves an active warning for that pair.
   */
  async applyCheckResults(input: {
    policy: string;
    results: { pair: [string, string]; status: string; kind?: string; evidence?: string }[];
  }): Promise<{ accepted: number; pairs: PairStatusView[]; createdWarnings: WarningRecord[] }> {
    const model = await this.load();
    const now = new Date().toISOString();
    const createdWarnings: WarningRecord[] = [];
    for (const result of input.results) {
      if (!Array.isArray(result.pair) || result.pair.length !== 2) {
        throw new Error("check result requires pair [a, b]");
      }
      const [a, b] = result.pair;
      if (!(a in model.agents) || !(b in model.agents)) {
        throw new Error(`unknown agent in pair ${a}|${b}`);
      }
      if (!RADAR_STATUSES.includes(result.status as RadarStatus)) {
        throw new Error(`invalid radar status: ${String(result.status)}`);
      }
      if (result.status === "not_checked") {
        throw new Error("runner results must be conflict|clean|unknown, not not_checked");
      }
      const vector = { a: model.heads[a], b: model.heads[b] };
      const record: PairCheckRecord = {
        key: pairKey(result.pair),
        pair: [a, b],
        status: result.status as RadarStatus,
        kind: result.kind,
        evidence: result.evidence,
        vector,
        at: now,
      };
      model.pairChecks[record.key] = record;
      this.pushRadarLog(model, {
        pair: [a, b],
        heads: vector,
        status: record.status,
        kind: record.kind,
        evidence: record.evidence,
      }, now);
      if (record.status === "conflict") {
        const warning = this.warningForPairAtHeads(model, [a, b], vector, record, input.policy, now);
        if (warning) {
          createdWarnings.push(warning);
        }
      } else if (record.status === "clean") {
        for (const warning of model.warnings) {
          if (
            warning.status === "active" &&
            pairKey(warning.pair) === record.key &&
            warning.headsAtIssue.a === vector.a &&
            warning.headsAtIssue.b === vector.b
          ) {
            warning.status = "invalidated";
            warning.invalidatedAt = now;
            warning.resolvedBy = `clean check (${input.policy})`;
          }
        }
      }
    }
    await this.persist();
    return { accepted: input.results.length, pairs: this.pairViews(model), createdWarnings };
  }

  private warningForPairAtHeads(
    model: CoordinatorModel,
    pair: [string, string],
    heads: { a: string; b: string },
    record: PairCheckRecord,
    policy: string,
    now: string,
  ): WarningRecord | null {
    const key = pairKey(pair);
    const existing = model.warnings.find(
      (warning) =>
        warning.status === "active" &&
        pairKey(warning.pair) === key &&
        warning.headsAtIssue.a === heads.a &&
        warning.headsAtIssue.b === heads.b,
    );
    if (existing) {
      return null;
    }
    model.warnSeq += 1;
    const warning: WarningRecord = {
      id: `warn-${model.warnSeq}`,
      pair,
      headsAtIssue: heads,
      reason: record.kind ?? "conflict",
      status: "active",
      createdAt: now,
      invalidatedAt: null,
      kind: record.kind,
      evidence: record.evidence ?? `policy ${policy}`,
      acks: [],
    };
    model.warnings.push(warning);
    if (model.warnings.length > WARNINGS_CAP) {
      model.warnings.splice(0, model.warnings.length - WARNINGS_CAP);
    }
    return warning;
  }

  private pushRadarLog(
    model: CoordinatorModel,
    entry: { pair: [string, string]; heads: { a: string; b: string }; status: RadarStatus; kind?: string; evidence?: string },
    now: string,
  ): void {
    model.radarLog.push({ at: now, ...entry });
    if (model.radarLog.length > RADAR_LOG_CAP) {
      model.radarLog.splice(0, model.radarLog.length - RADAR_LOG_CAP);
    }
  }

  private pairViews(model: CoordinatorModel): PairStatusView[] {
    const ids = Object.keys(model.heads).sort();
    const views: PairStatusView[] = [];
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const pair: [string, string] = [ids[i], ids[j]];
        const heads = { a: model.heads[ids[i]], b: model.heads[ids[j]] };
        const stored = model.pairChecks[pairKey(pair)];
        const fresh =
          stored !== undefined &&
          stored.vector.a === heads.a &&
          stored.vector.b === heads.b;
        views.push({
          pair,
          heads,
          status: fresh ? stored.status : "not_checked",
          kind: fresh ? stored.kind : undefined,
          evidence: fresh ? stored.evidence : undefined,
          checkedAt: stored ? stored.at : null,
          stale: stored !== undefined && !fresh,
          activeWarningIds: model.warnings
            .filter((warning) => warning.status === "active" && pairKey(warning.pair) === pairKey(pair))
            .map((warning) => warning.id),
        });
      }
    }
    return views;
  }

  private runRadar(
    model: CoordinatorModel,
    change: { agent: string; ref: string; sha: string; before: string | null },
  ): { checks: RadarPairResult[]; created: WarningRecord[] } {
    const siblings = Object.keys(model.heads);
    const checks = this.radar.onPush(change, model.heads, siblings);
    const now = new Date().toISOString();
    const created: WarningRecord[] = [];
    for (const check of checks) {
      this.pushRadarLog(model, check, now);
      // Warnings exist only for status "conflict" (codex C-1305 #1). The
      // in-Worker StubRadar reports not_checked; conflicts arrive via
      // applyCheckResults from the trusted runner.
      if (check.status === "conflict") {
        const record: PairCheckRecord = {
          key: pairKey(check.pair),
          pair: check.pair,
          status: check.status,
          kind: check.kind,
          evidence: check.evidence,
          vector: check.heads,
          at: now,
        };
        model.pairChecks[record.key] = record;
        const warning = this.warningForPairAtHeads(model, check.pair, check.heads, record, "radar-inline", now);
        if (warning) {
          created.push(warning);
        }
      }
    }
    return { checks, created };
  }
}
