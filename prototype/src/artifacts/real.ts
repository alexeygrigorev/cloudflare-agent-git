import type {
  ArtifactsCreateRepoResult,
  ArtifactsPort,
  ArtifactsTokenResult,
  CommitMetadata,
  CreateRepoOptions,
  ForkOptions,
  LogOptions,
  RepoName,
  RepoSummary,
  TokenScope,
} from "../types.js";

export interface ArtifactsRepoCapability {
  info(): Promise<{
    name: RepoName;
    defaultBranch: string;
    description: string | null;
    readOnly: boolean;
  }>;
  createToken(scope?: TokenScope, ttl?: number): Promise<ArtifactsTokenResult>;
  listTokens(): Promise<{ total: number; tokens: unknown[] }>;
  revokeToken(tokenOrId: string): Promise<boolean>;
  fork(name: RepoName, opts?: ForkOptions): Promise<ArtifactsCreateRepoResult>;
  log(opts?: LogOptions): Promise<CommitMetadata[]>;
  readCommit(hash: string): Promise<CommitMetadata | null>;
  readTree(hash: string): Promise<{ mode: string; type: string; name: string; hash: string }[] | null>;
  readBlob(hash: string): Promise<Blob | null>;
  readFile(args: { ref: string; path: string }): Promise<Blob | null>;
  [Symbol.dispose](): void;
}

export interface ArtifactsNamespaceBinding {
  create(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult>;
  get(name: RepoName): Promise<ArtifactsRepoCapability>;
  list(opts?: { limit?: number; cursor?: string }): Promise<{
    repos: RepoSummary[];
    cursor?: string;
  }>;
  import(params: {
    source: { url: string; branch?: string; depth?: number };
    target: { name: RepoName; opts?: CreateRepoOptions };
  }): Promise<ArtifactsCreateRepoResult>;
  delete(name: RepoName): Promise<boolean>;
}

export class RealArtifacts implements ArtifactsPort {
  private readonly binding: ArtifactsNamespaceBinding;

  constructor(binding: ArtifactsNamespaceBinding) {
    this.binding = binding;
  }

  async createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult> {
    return this.binding.create(name, opts);
  }

  async fork(source: RepoName, target: RepoName, opts?: ForkOptions): Promise<ArtifactsCreateRepoResult> {
    if (opts?.baseSha) {
      // No documented binding parameter forks at an arbitrary commit
      // (docs-notes ASSUMED-A): refuse instead of inventing an API.
      throw new Error("fork at explicit baseSha is UNSUPPORTED by the documented Artifacts binding");
    }
    using repo = await this.binding.get(source);
    return repo.fork(target, opts);
  }

  async mintToken(
    repo: RepoName,
    scope: TokenScope = "write",
    ttlSeconds = 3600,
  ): Promise<ArtifactsTokenResult> {
    using handle = await this.binding.get(repo);
    return handle.createToken(scope, ttlSeconds);
  }

  async log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]> {
    using handle = await this.binding.get(repo);
    return handle.log(opts);
  }

  async headCommit(repo: RepoName, ref = "HEAD"): Promise<string | null> {
    using handle = await this.binding.get(repo);
    // Only documented operations: log({ref, limit:1}) yields the tip commit.
    const commits = await handle.log({ ref, limit: 1 });
    return commits[0]?.id ?? null;
  }

  async hasCommit(repo: RepoName, sha: string): Promise<boolean> {
    using handle = await this.binding.get(repo);
    return (await handle.readCommit(sha)) !== null;
  }

  async listRepos(limit = 100): Promise<RepoSummary[]> {
    const page = await this.binding.list({ limit });
    return page.repos;
  }

  async deleteRepo(name: RepoName): Promise<boolean> {
    return this.binding.delete(name);
  }
}
