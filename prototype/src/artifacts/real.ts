import type {
  ArtifactsCreateRepoResult,
  ArtifactsPort,
  ArtifactsTokenResult,
  CommitMetadata,
  CreateRepoOptions,
  ForkOptions,
  ForkResult,
  LogOptions,
  RepoName,
  RepoSummary,
  TokenScope,
  UnprocessedPush,
} from "../types.js";
import {
  ArtifactsForkNotReadyError,
  normalizeArtifactsError,
  type ArtifactsError,
} from "./errors.js";
import { mapRawCommit, mapRawRepoSummary, type RawCommit } from "./map.js";

/**
 * REALITY notes (artifacts-spike, origin/proto/artifacts-spike @ c75faa1):
 *
 * - Commit fields over the real service are `{hash, treeHash, message,
 *   author, committer, parents[], authoredAt, committedAt}` with
 *   EPOCH-SECONDS instants — never `.id`/ISO `.timestamp` (finding B, REST
 *   evidence O13/O16). The capability below therefore exposes the RAW shape
 *   and RealArtifacts maps to port CommitMetadata at exactly one boundary
 *   (src/artifacts/map.ts). Binding type generation (`npx wrangler types`)
 *   is still UNVERIFIED — D stays open — but nothing here may assume the
 *   old id/ISO shape again.
 * - Tokens are OPAQUE. The real service issues `art_v2_x_<40
 *   hex>?expires=<unix>`, not the documented `art_v1_…` (finding 1): this
 *   adapter never validates, normalizes or trims a token string.
 * - Fork is default-branch only (F CONFIRMED, O9/O10/O13). Readiness is
 *   polled from the LIST response's `status` field — the ONLY place it
 *   exists (finding 2: single GET has no status) — with bounded retries.
 *   `last_push_at` stays null forever (finding 3) and is never consulted.
 * - Namespace creation and forks are REST/binding-only: the wrangler CLI
 *   has list/get subcommands but NO create/fork (finding 6). The Worker
 *   path uses the binding; the bootstrap script path uses
 *   src/artifacts/rest.ts (PLAN-L1-REAL §1).
 */

export interface ArtifactsRepoCapability {
  info(): Promise<{
    name: RepoName;
    defaultBranch: string;
    description: string | null;
    readOnly: boolean;
  }>;
  createToken(scope?: TokenScope, ttl?: number): Promise<ArtifactsTokenResult | { token: string; expires_at?: string | number }>;
  listTokens(): Promise<{ total: number; tokens: unknown[] }>;
  revokeToken(tokenOrId: string): Promise<boolean>;
  fork(name: RepoName, opts?: ForkOptions): Promise<ArtifactsCreateRepoResult>;
  /** RAW real-service shape (hash/epoch seconds) — mapped at the port boundary. */
  log(opts?: LogOptions): Promise<RawCommit[]>;
  readCommit(hash: string): Promise<RawCommit | null>;
  readTree(hash: string): Promise<{ mode: string; type: string; name: string; hash: string }[] | null>;
  readBlob(hash: string): Promise<Blob | null>;
  readFile(args: { ref: string; path: string }): Promise<Blob | null>;
  [Symbol.dispose](): void;
}

/** Raw LIST entry: `status` is present on real LIST responses (O17). */
export interface RawRepoListEntry {
  name: RepoName;
  status?: string;
}

export interface ArtifactsNamespaceBinding {
  create(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult>;
  get(name: RepoName): Promise<ArtifactsRepoCapability>;
  list(opts?: { limit?: number; cursor?: string }): Promise<{
    repos: RawRepoListEntry[];
    cursor?: string;
  }>;
  import(params: {
    source: { url: string; branch?: string; depth?: number };
    target: { name: RepoName; opts?: CreateRepoOptions };
  }): Promise<ArtifactsCreateRepoResult>;
  delete(name: RepoName): Promise<boolean>;
}

export interface RealArtifactsOptions {
  /**
   * Fork-readiness polling (spike: forks observed ready within ~2–4.5 s,
   * O9–O12). Defaults: 3 attempts × 2500 ms.
   */
  readiness?: {
    maxAttempts?: number;
    delayMs?: number;
  };
  /** Injectable sleeper for tests; default a real setTimeout. */
  sleep?: (ms: number) => Promise<void>;
  beforeOperation?: () => Promise<void>;
}

const DEFAULT_READINESS_ATTEMPTS = 3;
const DEFAULT_READINESS_DELAY_MS = 2500;

const defaultSleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

export function normalizeTokenResult(raw: unknown, requestedScope: TokenScope): ArtifactsTokenResult {
  if (typeof raw === "string") {
    return {
      plaintext: raw,
      expiresAt: new Date(Date.now() + 3600 * 1000).toISOString(),
      scope: requestedScope,
    };
  }
  const obj = raw as Record<string, unknown> | null | undefined;
  const plaintext = String(obj?.plaintext ?? obj?.token ?? "");
  let expiresAt = obj?.expiresAt ?? obj?.expires_at;
  if (typeof expiresAt === "number") {
    expiresAt = new Date(expiresAt < 1e11 ? expiresAt * 1000 : expiresAt).toISOString();
  } else if (!expiresAt || typeof expiresAt !== "string") {
    expiresAt = new Date(Date.now() + 3600 * 1000).toISOString();
  }
  const scope = (obj?.scope as TokenScope) || requestedScope;
  return {
    plaintext,
    expiresAt: String(expiresAt),
    scope,
  };
}

export class RealArtifacts implements ArtifactsPort {
  private readonly binding: ArtifactsNamespaceBinding;
  private readonly readinessMaxAttempts: number;
  private readonly readinessDelayMs: number;
  private readonly sleep: (ms: number) => Promise<void>;
  private readonly beforeOperation?: () => Promise<void>;

  constructor(binding: ArtifactsNamespaceBinding, options: RealArtifactsOptions = {}) {
    this.binding = binding;
    this.readinessMaxAttempts = options.readiness?.maxAttempts ?? DEFAULT_READINESS_ATTEMPTS;
    this.readinessDelayMs = options.readiness?.delayMs ?? DEFAULT_READINESS_DELAY_MS;
    this.sleep = options.sleep ?? defaultSleep;
    this.beforeOperation = options.beforeOperation;
  }

  /**
   * Error boundary for binding calls: the real binding's thrown shape is
   * UNVERIFIED (spike ASSUMED-D), so normalize only what carries
   * recognizable markers (status/code/envelope) and pass anything else
   * through untouched.
   */
  private async guarded<T>(fn: () => Promise<T>): Promise<T> {
    if (this.beforeOperation) {
      await this.beforeOperation();
    }
    try {
      return await fn();
    } catch (err) {
      const normalized = normalizeArtifactsError(err) as ArtifactsError | unknown;
      if (normalized instanceof Error && normalized !== err) {
        throw normalized;
      }
      throw err;
    }
  }

  private wrapCapability(repo: ArtifactsRepoCapability): ArtifactsRepoCapability {
    return {
      info: () => this.guarded(() => repo.info()),
      createToken: (scope, ttl) => this.guarded(() => repo.createToken(scope, ttl)),
      listTokens: () => this.guarded(() => repo.listTokens()),
      revokeToken: (tokenOrId) => this.guarded(() => repo.revokeToken(tokenOrId)),
      fork: (name, opts) => this.guarded(() => repo.fork(name, opts)),
      log: (opts) => this.guarded(() => repo.log(opts)),
      readCommit: (hash) => this.guarded(() => repo.readCommit(hash)),
      readTree: (hash) => this.guarded(() => repo.readTree(hash)),
      readBlob: (hash) => this.guarded(() => repo.readBlob(hash)),
      readFile: (args) => this.guarded(() => repo.readFile(args)),
      [Symbol.dispose]: () => {
        if (typeof repo[Symbol.dispose] === "function") {
          repo[Symbol.dispose]();
        }
      },
    };
  }

  private async getRepoCapability(name: RepoName): Promise<ArtifactsRepoCapability> {
    const raw = await this.guarded(() => this.binding.get(name));
    return this.wrapCapability(raw);
  }

  async createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult> {
    return this.guarded(() => this.binding.create(name, opts));
  }

  async fork(source: RepoName, target: RepoName, opts?: ForkOptions): Promise<ForkResult> {
    const { baseSha, ...bindingOpts } = opts ?? {};
    using repo = await this.getRepoCapability(source);
    const created = await repo.fork(target, Object.keys(bindingOpts).length > 0 ? bindingOpts : undefined);
    await this.waitForRepoReady(created.name);
    if (baseSha === undefined) {
      return created;
    }
    using fresh = await this.getRepoCapability(created.name);
    const head = await fresh.log({ limit: 1 });
    const realized = head.length > 0 ? mapRawCommit(head[0]).id : null;
    return { ...created, baseSha: realized ?? baseSha };
  }

  async waitForRepoReady(name: RepoName): Promise<void> {
    for (let attempt = 1; attempt <= this.readinessMaxAttempts; attempt += 1) {
      const page = await this.guarded(() => this.binding.list({ limit: 100 }));
      const entry: RawRepoListEntry | undefined = page.repos.find((repo) => repo.name === name);
      if (entry !== undefined && mapRawRepoSummary(entry).status === "ready") {
        return;
      }
      if (attempt < this.readinessMaxAttempts) {
        await this.sleep(this.readinessDelayMs);
      }
    }
    throw new ArtifactsForkNotReadyError(this.readinessMaxAttempts);
  }

  async mintToken(
    repo: RepoName,
    scope: TokenScope = "write",
    ttlSeconds = 3600,
  ): Promise<ArtifactsTokenResult> {
    using handle = await this.getRepoCapability(repo);
    const raw = await handle.createToken(scope, ttlSeconds);
    return normalizeTokenResult(raw, scope);
  }

  async log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]> {
    using handle = await this.getRepoCapability(repo);
    const raw = await handle.log(opts);
    return raw.map(mapRawCommit);
  }

  async headCommit(repo: RepoName, ref = "HEAD"): Promise<string | null> {
    using handle = await this.getRepoCapability(repo);
    const commits = await handle.log({ ref, limit: 1 });
    return commits.length > 0 ? mapRawCommit(commits[0]).id : null;
  }

  async hasCommit(repo: RepoName, sha: string): Promise<boolean> {
    using handle = await this.getRepoCapability(repo);
    return (await handle.readCommit(sha)) !== null;
  }

  async listRepos(limit = 100): Promise<RepoSummary[]> {
    const page = await this.guarded(() => this.binding.list({ limit }));
    return page.repos.map(mapRawRepoSummary);
  }

  async deleteRepo(name: RepoName): Promise<boolean> {
    return this.guarded(() => this.binding.delete(name));
  }

  async unprocessedPushes(): Promise<UnprocessedPush[]> {
    return [];
  }
}
