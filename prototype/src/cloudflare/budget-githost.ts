import type {
  GitHost,
  CreateRepoOptions,
  ForkOptions,
  ArtifactsCreateRepoResult,
  ForkResult,
  ArtifactsTokenResult,
  CommitMetadata,
  LogOptions,
  RepoSummary,
  RepoName,
  TokenScope,
  UnprocessedPush,
} from "../ports/githost.js";
import { BudgetTracker } from "./budget.js";

export class BudgetAwareGitHost implements GitHost {
  constructor(
    private readonly delegate: GitHost,
    private readonly tracker: BudgetTracker,
    private readonly state: DurableObjectState,
  ) {}

  private async rewriteRemote(result: ArtifactsCreateRepoResult): Promise<ArtifactsCreateRepoResult> {
    const upstreamUrl = result.remote;
    let gatewayToken = "internal_upstream_only";

    await this.state.storage.transaction(async (txn) => {
      await txn.put(`repo:${result.name}:upstream`, upstreamUrl);
      await txn.delete(`repo:${result.name}:pending`);
      
      const canonical = await txn.get("canonical:repo");
      if (!canonical) {
        gatewayToken = `gw_${crypto.randomUUID()}`;
        const ttlSeconds = 3600; // short TTL
        const expiresAt = new Date(Date.now() + ttlSeconds * 1000).toISOString();
        await txn.put(`token:${gatewayToken}`, {
          realToken: result.token,
          repo: result.name,
          scope: "write",
          expiresAt: expiresAt,
          createdAt: new Date().toISOString(),
        });
        await txn.put("canonical:repo", result.name);
        await txn.put("canonical:token", gatewayToken);
      }
    });

    return {
      ...result,
      remote: `/git/${result.name}.git`,
      token: gatewayToken,
    };
  }

  async createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult> {
    await this.tracker.reserveRepoSlot(name);
    if (this.delegate.constructor.name !== "RealArtifacts") {
      await this.tracker.reserveOp();
    }
    try {
      const result = await this.delegate.createRepo(name, opts);
      return await this.rewriteRemote(result);
    } catch (err) {
      throw err;
    }
  }

  async fork(source: RepoName, target: RepoName, opts?: ForkOptions): Promise<ForkResult> {
    await this.tracker.reserveRepoSlot(target);
    if (this.delegate.constructor.name !== "RealArtifacts") {
      await this.tracker.reserveOp();
    }
    try {
      const result = await this.delegate.fork(source, target, opts);
      const rewritten = await this.rewriteRemote(result);
      return { ...rewritten, baseSha: result.baseSha };
    } catch (err) {
      throw err;
    }
  }

  async mintToken(repo: RepoName, scope?: TokenScope, ttlSeconds?: number): Promise<ArtifactsTokenResult> {
    if (this.delegate.constructor.name !== "RealArtifacts") {
      await this.tracker.reserveOp();
    }
    const realToken = await this.delegate.mintToken(repo, scope, ttlSeconds);
    const gatewayToken = `gw_${crypto.randomUUID()}`;
    const ttl = ttlSeconds ?? 3600;
    const expiresAt = realToken.expiresAt ?? new Date(Date.now() + ttl * 1000).toISOString();

    await this.state.storage.put(`token:${gatewayToken}`, {
      realToken: realToken.plaintext,
      repo,
      scope: scope || "write",
      expiresAt: expiresAt,
      createdAt: new Date().toISOString(),
    });

    return {
      plaintext: gatewayToken,
      expiresAt: expiresAt,
      scope: realToken.scope,
    };
  }

  async log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]> {
    return this.delegate.log(repo, opts);
  }

  async headCommit(repo: RepoName, ref?: string): Promise<string | null> {
    return this.delegate.headCommit(repo, ref);
  }

  async hasCommit(repo: RepoName, sha: string): Promise<boolean> {
    return this.delegate.hasCommit(repo, sha);
  }

  async listRepos(limit?: number): Promise<RepoSummary[]> {
    if (this.delegate.constructor.name !== "RealArtifacts") await this.tracker.reserveOp();
    const repos = await this.delegate.listRepos(limit);
    const known = new Set(repos.map((repo) => repo.name));
    const records = await this.state.storage.list({ prefix: "repo:" });
    for (const key of records.keys()) {
      const match = /^repo:([^:]+):(upstream|pending)$/.exec(key);
      if (match && !known.has(match[1])) {
        repos.push({ name: match[1], status: "importing" });
        known.add(match[1]);
      }
    }
    return repos;
  }

  async deleteRepo(name: RepoName): Promise<boolean> {
    if (this.delegate.constructor.name !== "RealArtifacts") await this.tracker.reserveOp();
    let ok: boolean;
    try {
      ok = await this.delegate.deleteRepo(name);
    } catch (error) {
      if (!(error instanceof Error && (error.name === "ArtifactsNotFoundError" || error.message.startsWith("repo not found")))) throw error;
      ok = false; // Already absent: still remove this repository's stale gateway records.
    }
    {
      await this.state.storage.transaction(async (txn) => {
        await txn.delete(`repo:${name}:upstream`);
        await txn.delete(`repo:${name}:pending`);
        const tokens = await txn.list({ prefix: "token:" });
        for (const [key, value] of tokens) {
          if (value && typeof value === "object" && (value as any).repo === name) await txn.delete(key);
        }
        if (await txn.get("canonical:repo") === name) {
          await txn.delete("canonical:repo");
          await txn.delete("canonical:token");
          await txn.delete("canonical:upstream_token");
        }
      });
    }
    return ok;
  }

  unprocessedPushes(): Promise<UnprocessedPush[]> {
    if (this.delegate.unprocessedPushes) {
      return this.delegate.unprocessedPushes();
    }
    return Promise.resolve([]);
  }
}
