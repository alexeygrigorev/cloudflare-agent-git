import { DurableObject } from "cloudflare:workers";
import { RealArtifacts } from "./artifacts/real.js";
import { SidecarArtifacts } from "./artifacts/sidecar.js";
import {
  type ChecksCoverageCounts,
  type ChecksPolicySpec,
  type EvidenceBag,
  type NormalizedCheckResult,
  type NormalizedChecksPayload,
} from "./checks-wire.js";
import { RADAR_STATUSES, pairKey, radarFromEnv, type Radar, type RadarPairResult, type RadarStatus } from "./radar.js";
import type { UnprocessedPush } from "./types.js";

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
  /** Summary string (0.0 evidence, or 0.1 evidence.summary chain). */
  evidence?: string;
  /** C-1350: verbatim typed evidence object served on the pair view (0.1). */
  evidenceDetail?: EvidenceBag;
  /** C-1350: combined tests the runner collected for this pair, when reported. */
  testsCollected?: number;
  vector: { a: string; b: string };
  at: string;
}

/** Derived per-pair view for /status: fresh results only; stale => not_checked. */
export interface PairStatusView {
  pair: [string, string];
  /** C-1350: heads keyed by agentId (was positional {a, b}). */
  heads: Record<string, string>;
  status: RadarStatus;
  kind?: string;
  /** C-1350: string (0.0) or verbatim typed evidence object (0.1). Must stay
   * EvidenceBag, not Record<string, unknown>: an unknown-valued index
   * signature collapses the typed-RPC stub method to `never`. */
  evidence?: string | EvidenceBag;
  /** C-1350: per-pair coverage of the FRESH check (L4 gate: clean counts only
   * with tests_collected > 0 at current heads); omitted when stale. */
  coverage?: { tests_collected: number };
  checkedAt: string | null;
  /** True when a stored check exists but no longer matches the current heads. */
  stale: boolean;
  /** codex C-1357: set while a member agent has an unprocessed push — the
   * pair's true head state is unknown, so nothing presents as current. */
  unprocessedReason?: string;
  activeWarningIds: string[];
}

const CANONICAL_BASE = "agent-branches-canonical";
const RADAR_LOG_CAP = 50;
const WARNINGS_CAP = 200;

/** muse-r46 D2: per-agent bound on the push-dedup ring (latest N accepted pushes). */
export const SEEN_PUSHES_CAP_PER_AGENT = 16;

export interface RunnerReport {
  /** Verbatim: the 0.0 policy string or the 0.1 policy object (C-1350). */
  policy: string | ChecksPolicySpec;
  /** Verbatim: the 0.0 string[] or the 0.1 counts object (C-1350). */
  coverage: string[] | ChecksCoverageCounts;
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
  /**
   * muse-r46 D2: bounded push-dedup memory — per agent, the latest
   * SEEN_PUSHES_CAP_PER_AGENT accepted "sha" values. The current head is
   * always deduped via the heads check; older ring entries catch out-of-
   * order webhook redelivery within a bounded window.
   */
  seenPushes: Record<string, string[]>;
  /**
   * muse-r46 AUTH: SHA-256 digest of each agent's per-task write token
   * (minted at task creation). The plaintext is returned once to the caller
   * and never persisted or logged.
   */
  agentTokenHashes: Record<string, string>;
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
    seenPushes: {},
    agentTokenHashes: {},
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

/** SHA-256 of a string as lowercase hex (token digests; never the token itself). */
export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Constant-time compare; callers pass equal-length hex digests. */
export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * muse-r46 D1: a pair may arrive in either agent order ([a,b] or [b,a]);
 * canonicalize the pair AND its per-slot heads (same a <= b rule as pairKey)
 * so both orders map to ONE pairChecks record and at most ONE active
 * warning for a pair at a given head vector.
 */
function canonicalPairHeads(
  pair: readonly [string, string],
  heads: { a: string; b: string },
): { pair: [string, string]; heads: { a: string; b: string } } {
  return pair[0] <= pair[1]
    ? { pair: [pair[0], pair[1]], heads: { a: heads.a, b: heads.b } }
    : { pair: [pair[1], pair[0]], heads: { a: heads.b, b: heads.a } };
}

export class Coordinator extends DurableObject {
  private readonly state: DurableObjectState;
  private readonly radar: Radar;
  private model: CoordinatorModel | null = null;
  /**
   * Serializes mutating RPC methods (codex C-1305 #4): workerd can deliver
   * concurrent events while a method awaits sidecar/binding I/O, which would
   * otherwise race seq allocation and cause duplicate forks or lost updates.
   */
  private mutex: Promise<unknown> = Promise.resolve();

  constructor(state: DurableObjectState, env: Env) {
    super(state, env);
    this.state = state;
    this.radar = radarFromEnv(env.RADAR_IMPL);
  }

  private serialized<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.mutex.then(fn, fn);
    this.mutex = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
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
    // muse-r46 D2: pre-0.1.1 models kept one flat "agentId:sha" array;
    // regroup it into the bounded per-agent ring.
    if (Array.isArray(this.model.seenPushes)) {
      const legacy = this.model.seenPushes as unknown as string[];
      const perAgent: Record<string, string[]> = {};
      for (const key of legacy) {
        const sep = key.indexOf(":");
        const agent = sep === -1 ? key : key.slice(0, sep);
        (perAgent[agent] ??= []).push(key);
      }
      for (const agent of Object.keys(perAgent)) {
        perAgent[agent] = perAgent[agent].slice(-SEEN_PUSHES_CAP_PER_AGENT);
      }
      this.model.seenPushes = perAgent;
    }
    // muse-r46 AUTH: agents created before 0.1.1 have no stored digest.
    this.model.agentTokenHashes ??= {};
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

  private async setupNow(): Promise<{
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

  private async createTaskNow(input: {
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
      await this.setupNow();
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
    // muse-r46 D3: real mode may not honor the requested base (the binding
    // forks the default branch, ASSUMED-F); record the REALIZED base.
    const effectiveBaseSha = fork.baseSha ?? baseSha;
    const token = await port.mintToken(forkName, "write", input.ttlSeconds ?? 3600);
    // muse-r46 AUTH: store only the digest for later verification of
    // agent-authenticated routes (/events/push, /tasks/:id/tests, acks).
    model.agentTokenHashes[agentId] = await sha256Hex(token.plaintext);
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
      baseSha: effectiveBaseSha,
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
      base_sha: effectiveBaseSha,
      intent: input.intent ?? null,
      token: { scope: token.scope, expiresAt: token.expiresAt, plaintext: token.plaintext },
      head,
    };
  }

  private async recordPushNow(input: {
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
    // muse-r46 D2: bounded per-agent ring instead of an ever-growing array
    // (the old `seenPushes.includes` was O(total pushes) per request).
    let seen = model.seenPushes[agentId];
    if (!seen) {
      seen = model.seenPushes[agentId] = [];
    }
    const deduped = seen.includes(dedupKey) || model.heads[agentId] === input.sha;
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
    seen.push(dedupKey);
    if (seen.length > SEEN_PUSHES_CAP_PER_AGENT) {
      seen.splice(0, seen.length - SEEN_PUSHES_CAP_PER_AGENT);
    }
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
    /** codex C-1357: pushes the Worker never accepted (callback lost). */
    unprocessedPushes: (UnprocessedPush & { agentId: string | null })[];
  }> {
    const model = await this.load();
    const unprocessed = await this.unprocessedPushesSafe();
    const unprocessedAgents = new Set(
      unprocessed
        .map((push) => this.agentForFork(model, push.repo)?.agentId ?? null)
        .filter((agentId): agentId is string => agentId !== null),
    );
    return {
      canonical: { name: model.canonicalName, remote: model.canonicalRemote },
      agents: Object.values(model.agents),
      heads: model.heads,
      pairs: this.pairViews(model, unprocessedAgents),
      warnings: [...model.warnings]
        .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
        .slice(0, 20),
      radarLog: [...model.radarLog].slice(-20).reverse(),
      lastRunnerReport: model.lastRunnerReport,
      unprocessedPushes: unprocessed.map((push) => ({
        ...push,
        agentId: this.agentForFork(model, push.repo)?.agentId ?? null,
      })),
    };
  }

  private agentForFork(model: CoordinatorModel, repo: string): AgentRecord | undefined {
    return Object.values(model.agents).find((agent) => agent.forkName === repo || agent.forkRemote === repo);
  }

  /**
   * codex C-1357: pulls the sidecar's callback-loss ledger. A failing or
   * absent ledger must never break /status — an unreadable guard degrades to
   * the pre-guard behavior, it does not fabricate certainty.
   */
  private async unprocessedPushesSafe(): Promise<UnprocessedPush[]> {
    try {
      return (await this.port().unprocessedPushes?.()) ?? [];
    } catch {
      return [];
    }
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
  private async ackWarningNow(
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
  private async recordTestProvenanceNow(
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

  async setup(): Promise<ReturnType<Coordinator["setupNow"]>> {
    return this.serialized(() => this.setupNow());
  }

  async createTask(input: Parameters<Coordinator["createTaskNow"]>[0]): Promise<ReturnType<Coordinator["createTaskNow"]>> {
    return this.serialized(() => this.createTaskNow(input));
  }

  async recordPush(input: Parameters<Coordinator["recordPushNow"]>[0]): Promise<ReturnType<Coordinator["recordPushNow"]>> {
    return this.serialized(() => this.recordPushNow(input));
  }

  async ackWarning(
    warningId: string,
    input: Parameters<Coordinator["ackWarningNow"]>[1],
  ): Promise<ReturnType<Coordinator["ackWarningNow"]>> {
    return this.serialized(() => this.ackWarningNow(warningId, input));
  }

  async recordTestProvenance(
    taskId: string,
    input: Parameters<Coordinator["recordTestProvenanceNow"]>[1],
  ): Promise<ReturnType<Coordinator["recordTestProvenanceNow"]>> {
    return this.serialized(() => this.recordTestProvenanceNow(taskId, input));
  }

  /**
   * muse-r46 AUTH: which agent (if any) owns this presented per-task token.
   * Returns null for unknown/garbage tokens; digests are compared
   * constant-time and the plaintext is never stored.
   */
  async credentialAgent(presented: string): Promise<string | null> {
    const model = await this.load();
    const digest = await sha256Hex(presented);
    for (const [agentId, hash] of Object.entries(model.agentTokenHashes)) {
      if (timingSafeEqual(digest, hash)) {
        return agentId;
      }
    }
    return null;
  }

  /** Owning agent of a task, or null for unknown tasks (route: /tasks/:id/tests). */
  async taskOwner(taskId: string): Promise<string | null> {
    const task = (await this.load()).tasks[taskId];
    return task ? task.agentId : null;
  }

  /** Owning agent of a fork (by name or remote), or null (route: /events/push). */
  async forkOwner(fork: string): Promise<string | null> {
    const model = await this.load();
    const record = Object.values(model.agents).find(
      (candidate) => candidate.forkName === fork || candidate.forkRemote === fork,
    );
    return record ? record.agentId : null;
  }

  async submitChecks(
    input: Parameters<Coordinator["submitChecksNow"]>[0],
  ): Promise<ReturnType<Coordinator["submitChecksNow"]>> {
    return this.serialized(() => this.submitChecksNow(input));
  }

  async applyCheckResults(
    input: Parameters<Coordinator["applyCheckResultsNow"]>[0],
  ): Promise<ReturnType<Coordinator["applyCheckResultsNow"]>> {
    return this.serialized(() => this.applyCheckResultsNow(input));
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
  private async submitChecksNow(input: NormalizedChecksPayload): Promise<
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
    const applied = await this.applyCheckResultsNow({ policy: input.policy, results: input.results });
    const model2 = await this.load();
    const runnerReport: RunnerReport = {
      policy: input.policyVerbatim,
      coverage: input.coverageVerbatim ?? [],
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
  private async applyCheckResultsNow(input: {
    policy: string;
    results: NormalizedCheckResult[];
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
      // C-1350: per-result heads VALUES (0.1 wire) must agree with the heads
      // the vector declared. Checked here, after submitChecksNow's stale
      // gate, so a stale submission still gets its 409 — parser shape checks
      // stay 400s, value disagreements are 400s only for a CURRENT vector.
      if (result.heads) {
        for (const agent of result.pair) {
          if (result.heads[agent] !== model.heads[agent]) {
            throw new Error(`result heads for ${agent} disagree with the submitted vector`);
          }
        }
      }
      // muse-r46 D1: canonical order before deriving the vector, so a
      // reversed pair overwrites/refreshes the same record instead of
      // duplicating warnings or storing a slot-flipped vector.
      const ordered = canonicalPairHeads(result.pair, { a: model.heads[result.pair[0]], b: model.heads[result.pair[1]] });
      const pair = ordered.pair;
      const vector = ordered.heads;
      const record: PairCheckRecord = {
        key: pairKey(pair),
        pair,
        status: result.status as RadarStatus,
        kind: result.kind,
        evidence: result.evidence,
        evidenceDetail: result.evidenceDetail,
        testsCollected: result.testsCollected,
        vector,
        at: now,
      };
      model.pairChecks[record.key] = record;
      this.pushRadarLog(model, {
        pair,
        heads: vector,
        status: record.status,
        kind: record.kind,
        evidence: record.evidence,
      }, now);
      if (record.status === "conflict") {
        const warning = this.warningForPairAtHeads(model, pair, vector, record, input.policy, now);
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
    // muse-r46 D1: canonicalize the incoming pair/heads so the duplicate
    // lookup and the stored headsAtIssue are slot-order independent, no
    // matter what order the radar/runner reported.
    const ordered = canonicalPairHeads(pair, heads);
    const key = pairKey(ordered.pair);
    const existing = model.warnings.find(
      (warning) =>
        warning.status === "active" &&
        pairKey(warning.pair) === key &&
        warning.headsAtIssue.a === ordered.heads.a &&
        warning.headsAtIssue.b === ordered.heads.b,
    );
    if (existing) {
      return null;
    }
    model.warnSeq += 1;
    const warning: WarningRecord = {
      id: `warn-${model.warnSeq}`,
      pair: ordered.pair,
      headsAtIssue: ordered.heads,
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

  private pairViews(model: CoordinatorModel, unprocessedAgents: ReadonlySet<string> = new Set()): PairStatusView[] {
    const ids = Object.keys(model.heads).sort();
    const views: PairStatusView[] = [];
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const pair: [string, string] = [ids[i], ids[j]];
        const heads: Record<string, string> = { [ids[i]]: model.heads[ids[i]], [ids[j]]: model.heads[ids[j]] };
        const stored = model.pairChecks[pairKey(pair)];
        const fresh =
          stored !== undefined &&
          stored.vector.a === heads[ids[i]] &&
          stored.vector.b === heads[ids[j]];
        // codex C-1357: while an agent has an unprocessed push, its TRUE head
        // is unknown — the Worker never accepted the move. Any stored check
        // (however fresh it looks against the known heads) must NOT present
        // as current: the pair is not_checked with a reason, never clean.
        const uncertain = unprocessedAgents.has(ids[i]) || unprocessedAgents.has(ids[j]);
        views.push({
          pair,
          heads,
          status: uncertain ? "not_checked" : fresh ? stored.status : "not_checked",
          kind: fresh && !uncertain ? stored.kind : undefined,
          evidence: fresh && !uncertain ? (stored.evidenceDetail ?? stored.evidence) : undefined,
          coverage:
            fresh && !uncertain && typeof stored.testsCollected === "number"
              ? { tests_collected: stored.testsCollected }
              : undefined,
          checkedAt: stored ? stored.at : null,
          stale: (stored !== undefined && !fresh) || (fresh && uncertain),
          unprocessedReason: uncertain
            ? "an agent in this pair has an unprocessed push (Worker callback failed after bounded sidecar retries); its true head is unknown"
            : undefined,
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
        // muse-r46 D1: canonical order here too — the StubRadar emits pairs
        // in heads-iteration order, not sorted order.
        const ordered = canonicalPairHeads(check.pair, check.heads);
        const record: PairCheckRecord = {
          key: pairKey(ordered.pair),
          pair: ordered.pair,
          status: check.status,
          kind: check.kind,
          evidence: check.evidence,
          vector: ordered.heads,
          at: now,
        };
        model.pairChecks[record.key] = record;
        const warning = this.warningForPairAtHeads(model, ordered.pair, ordered.heads, record, "radar-inline", now);
        if (warning) {
          created.push(warning);
        }
      }
    }
    return { checks, created };
  }
}
