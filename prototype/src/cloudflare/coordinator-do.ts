import { DurableObject } from "cloudflare:workers";
import type {
  CreateTaskInput,
  CreateTaskResult,
  RecordPushInput,
  RecordPushResult,
  SetupResult,
  StatusResult,
  StaleChecksResult,
  SubmitChecksResult,
  TaskDetail,
} from "../core/coordinator.js";
import { CoordinatorCore } from "../core/coordinator.js";
import type { NormalizedCheckResult, NormalizedChecksPayload } from "../checks-wire.js";
import { cryptoIds, systemClock } from "../ports/clock.js";
import type { PairStatusView, WarningRecord } from "../core/model.js";
import { radarFromEnv } from "../radar.js";
import { DurableObjectCoordinationStore } from "./do-store.js";
import { gitHostFromEnv } from "./githost.js";
import { BudgetTracker } from "./budget.js";
import { BudgetAwareGitHost } from "./budget-githost.js";
import { RealArtifacts } from "../artifacts/real.js";
import type { GitHost } from "../ports/githost.js";

export class Coordinator extends DurableObject {
  private readonly core: CoordinatorCore;
  private readonly budgetTracker: BudgetTracker;

  constructor(state: DurableObjectState, env: Env) {
    super(state, env);
    this.budgetTracker = new BudgetTracker(state, {
      maxDailyOps: env.MAX_DAILY_OPS !== undefined ? env.MAX_DAILY_OPS : env.BUDGET_MAX_DAILY_OPS,
      maxMonthlyOps: env.MAX_MONTHLY_OPS !== undefined ? env.MAX_MONTHLY_OPS : env.BUDGET_MAX_MONTHLY_OPS,
      maxRepos: env.MAX_REPOS !== undefined ? env.MAX_REPOS : env.BUDGET_MAX_REPOS,
      maxTotalBytes: env.MAX_TOTAL_BYTES !== undefined ? env.MAX_TOTAL_BYTES : env.BUDGET_MAX_TOTAL_BYTES,
      maxBodyBytes: env.MAX_BODY_BYTES !== undefined ? env.MAX_BODY_BYTES : env.BUDGET_MAX_BODY_BYTES,
    });

    const realOpts = {
      readiness: { maxAttempts: 3, delayMs: 2500 },
      beforeOperation: async () => {
        await this.budgetTracker.reserveOp();
      },
    };

    let gitHost: GitHost;
    if (env.ARTIFACTS) {
      const real = new RealArtifacts(env.ARTIFACTS, realOpts);
      gitHost = new BudgetAwareGitHost(real, this.budgetTracker, state);
    } else if (env.ENFORCE_CLOUD_BUDGET) {
      const base = gitHostFromEnv(env, realOpts);
      gitHost = new BudgetAwareGitHost(base, this.budgetTracker, state);
    } else {
      // Local sidecar fallback: unconstrained for local node/sidecar test suites
      gitHost = gitHostFromEnv(env);
    }

    this.core = new CoordinatorCore({
      store: new DurableObjectCoordinationStore(state),
      git: gitHost,
      radar: radarFromEnv(env.RADAR_IMPL),
      clock: systemClock,
      ids: cryptoIds,
    });
  }

  // Budget RPCs
  async getBudgetStats() {
    return this.budgetTracker.getStats();
  }

  async resolveGatewayToken(
    token: string,
    requestedRepo?: string,
  ): Promise<{ realToken: string; upstreamRemote: string; repo: string; scope: string } | null> {
    if (!token) return null;

    // Canonical admin seed: ADMIN_TOKEN is authorized for the canonical repo
    if (this.env.ADMIN_TOKEN && token === this.env.ADMIN_TOKEN) {
      const canonicalName = await this.ctx.storage.get<string>("canonical:repo");
      if (!canonicalName) return null;
      if (requestedRepo && requestedRepo !== canonicalName) {
        return null;
      }
      const upstreamUrl = await this.ctx.storage.get<string>(`repo:${canonicalName}:upstream`);
      if (!upstreamUrl) return null;

      const canonicalTokenId = await this.ctx.storage.get<string>("canonical:token");
      if (!canonicalTokenId) return null;

      const tokenInfo = await this.ctx.storage.get<{
        realToken: string;
        repo: string;
        scope: string;
        expiresAt?: number | string;
        agentId?: string;
        revoked?: boolean;
      }>(`token:${canonicalTokenId}`);

      if (!tokenInfo || tokenInfo.revoked) return null;
      if (!validExpiry(tokenInfo.expiresAt)) return null;

      if (
        typeof tokenInfo.realToken !== "string" ||
        !tokenInfo.realToken ||
        tokenInfo.repo !== canonicalName ||
        tokenInfo.scope !== "write"
      ) {
        return null;
      }

      return {
        realToken: tokenInfo.realToken,
        upstreamRemote: upstreamUrl,
        repo: canonicalName,
        scope: "write",
      };
    }

    const tokenInfo = await this.ctx.storage.get<{
      realToken: string;
      repo: string;
      scope: string;
      expiresAt?: number | string;
      agentId?: string;
      revoked?: boolean;
    }>(`token:${token}`);

    if (!tokenInfo || tokenInfo.revoked) return null;
    if (requestedRepo && tokenInfo.repo !== requestedRepo) return null;

    const upstreamUrl = await this.ctx.storage.get<string>(`repo:${tokenInfo.repo}:upstream`);
    if (!upstreamUrl) return null;

    // Validate expiration: parse ISO string or numeric timestamp correctly
    if (!validExpiry(tokenInfo.expiresAt)) return null;
    if (typeof tokenInfo.realToken !== "string" || !tokenInfo.realToken ||
        typeof tokenInfo.repo !== "string" || !tokenInfo.repo ||
        !["read", "write"].includes(tokenInfo.scope)) return null;

    // orphan task credentials cannot authorize
    if (!tokenInfo.agentId) {
      return null;
    }

    // Link task gateway auth to core revoked identity
    const activeAgent = await this.core.credentialAgent(token);
    if (!activeAgent || activeAgent !== tokenInfo.agentId) {
      return null;
    }

    if (await this.core.forkOwner(tokenInfo.repo) !== activeAgent) {
      return null;
    }

    return {
      realToken: tokenInfo.realToken,
      upstreamRemote: upstreamUrl,
      repo: tokenInfo.repo,
      scope: tokenInfo.scope,
    };
  }

  async reserveGitOperation(): Promise<void> {
    await this.budgetTracker.reserveOp();
  }

  async reserveGitBytes(bytes: number): Promise<void> {
    await this.budgetTracker.reserveBytes(bytes);
  }

  async deleteDemoRepos(): Promise<number> {
    const reposMap = await this.ctx.storage.list({ prefix: "repo:" });
    const repoNames = new Set<string>();
    for (const key of reposMap.keys()) {
      const match = /^repo:([^:]+):(upstream|pending)$/.exec(key);
      if (match) repoNames.add(match[1]);
    }

    const realOpts = {
      readiness: { maxAttempts: 3, delayMs: 2500 },
    };
    const gitHost = gitHostFromEnv(this.env, realOpts);
    let deleted = 0;
    const successfullyDeleted = new Set<string>();
    let firstError: unknown = null;

    for (const name of repoNames) {
      let ok = false;
      try {
        await this.budgetTracker.reserveOp();
        ok = await gitHost.deleteRepo(name);
      } catch (err) {
        // Only ignore NotFound errors, propagate BudgetError and others!
        if (
          (err && (err as any).name === "ArtifactsNotFoundError") ||
          (err && err instanceof Error && err.message.includes("repo not found"))
        ) {
          ok = true;
        } else {
          if (!firstError) firstError = err;
        }
      }
      if (ok) {
        successfullyDeleted.add(name);
        deleted++;
      }
    }

    // Atomic persistence of cleaned inventory and credentials
    let completelyCleaned = false;
    await this.ctx.storage.transaction(async (txn) => {
      for (const name of successfullyDeleted) {
        await txn.delete(`repo:${name}:upstream`);
        await txn.delete(`repo:${name}:pending`);
      }
      const remainingRepos = await txn.list({ prefix: "repo:" });
      let remainingCount = 0;
      for (const k of remainingRepos.keys()) {
        if (/^repo:([^:]+):(upstream|pending)$/.test(k)) {
          remainingCount++;
        }
      }

      if (remainingCount === 0) {
        completelyCleaned = true;
        await txn.delete("canonical:repo");
        await txn.delete("canonical:token");
        await txn.delete("canonical:upstream_token");
        // Clear all gateway credentials
        const tokens = await txn.list({ prefix: "token:" });
        for (const tokenKey of tokens.keys()) {
          await txn.delete(tokenKey);
        }
        // Clear core model from storage
        await txn.delete("model");
      } else {
        // Remove tokens for deleted repos
        const tokens = await txn.list({ prefix: "token:" });
        for (const [key, val] of tokens.entries()) {
          if (val && typeof val === "object" && successfullyDeleted.has((val as any).repo)) {
            await txn.delete(key);
          }
        }
      }
      // BUDGET COUNTERS ARE NEVER RESET!
    });

    if (completelyCleaned) {
      // Reset in-memory core model and cache!
      this.core.clearModel();
    }

    if (firstError) {
      throw firstError;
    }

    return deleted;
  }

  // Core RPC wrappers
  async setup(): Promise<SetupResult> {
    return this.core.setup();
  }

  async createTask(input: CreateTaskInput): Promise<CreateTaskResult> {
    const result = await this.core.createTask(input);
    if (result.token?.plaintext) {
      const key = `token:${result.token.plaintext}`;
      const existing = await this.ctx.storage.get<any>(key);
      if (existing) {
        existing.agentId = result.agentId;
        existing.taskId = result.taskId;
        await this.ctx.storage.put(key, existing);
      }
    }
    return result;
  }

  recordPush(input: RecordPushInput): Promise<RecordPushResult> {
    return this.core.recordPush(input);
  }

  status(): Promise<StatusResult> {
    return this.core.status();
  }

  snapshot(): Promise<any> {
    return this.core.snapshot();
  }

  getTask(taskId: string): Promise<TaskDetail> {
    return this.core.getTask(taskId);
  }

  ackWarning(warningId: string, input: { agent: string; note?: string }): Promise<{ warning: WarningRecord }> {
    return this.core.ackWarning(warningId, input);
  }

  recordTestProvenance(
    taskId: string,
    input: { command: string; exit: number; head_sha: string },
  ): Promise<{ testProvenance: TaskDetail["testProvenance"] }> {
    return this.core.recordTestProvenance(taskId, input);
  }

  submitChecks(input: NormalizedChecksPayload): Promise<SubmitChecksResult | StaleChecksResult> {
    return this.core.submitChecks(input);
  }

  applyCheckResults(input: {
    policy: string;
    results: NormalizedCheckResult[];
  }): Promise<{ accepted: number; pairs: PairStatusView[]; createdWarnings: WarningRecord[] }> {
    return this.core.applyCheckResults(input);
  }

  credentialAgent(presented: string, nowMs?: number): Promise<string | null> {
    return this.core.credentialAgent(presented, nowMs);
  }

  async revokeAgentToken(agentId: string, revokedAt?: string): Promise<boolean> {
    const revoked = await this.core.revokeAgentToken(agentId, revokedAt);
    await this.ctx.storage.transaction(async (txn) => {
      const tokens = await txn.list({ prefix: "token:" });
      for (const [key, val] of tokens.entries()) {
        const info = val as any;
        if (info && info.agentId === agentId) {
          info.revoked = true;
          info.revokedAt = revokedAt || new Date().toISOString();
          await txn.put(key, info);
        }
      }
    });
    return revoked;
  }

  taskOwner(taskId: string): Promise<string | null> {
    return this.core.taskOwner(taskId);
  }

  forkOwner(fork: string): Promise<string | null> {
    return this.core.forkOwner(fork);
  }
}

function validExpiry(value: unknown): boolean {
  const expiry = typeof value === "number"
    ? (value < 1e11 ? value * 1000 : value)
    : typeof value === "string" && value.length > 0 ? Date.parse(value) : NaN;
  return Number.isFinite(expiry) && expiry > Date.now();
}
