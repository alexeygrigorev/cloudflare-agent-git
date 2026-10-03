export type RepoName = string;

export type TokenScope = "read" | "write";

export interface CreateRepoOptions {
  description?: string;
  readOnly?: boolean;
  setDefaultBranch?: string;
}

export interface ForkOptions {
  description?: string;
  readOnly?: boolean;
  defaultBranchOnly?: boolean;
  /**
   * Fork starting at this commit of the source's default branch instead of
   * its tip (codex C-1306 base_sha). Local mode realizes it exactly with
   * ordinary git ref updates. The documented Cloudflare binding has no such
   * parameter (docs-notes ASSUMED-F): RealArtifacts forks the default
   * branch and reports the realized base on the ForkResult (muse-r46 D3).
   */
  baseSha?: string;
}

export interface ArtifactsCreateRepoResult {
  name: RepoName;
  remote: string;
  defaultBranch: string;
  token: string;
}

/**
 * Port-level fork result: the documented binding result plus, when
 * ForkOptions.baseSha was requested, the commit the fork ACTUALLY starts at
 * (muse-r46 D3). Implementations that honor baseSha exactly (local sidecar)
 * may omit it; RealArtifacts reports the fork's head at creation
 * (docs-notes ASSUMED-F) so the coordinator records the real base.
 */
export interface ForkResult extends ArtifactsCreateRepoResult {
  baseSha?: string;
}

export interface ArtifactsTokenResult {
  plaintext: string;
  expiresAt: string;
  scope: TokenScope;
}

export interface GitAuthor {
  name: string;
  email: string;
}

export interface CommitMetadata {
  id: string;
  message: string;
  timestamp: string;
  parents: string[];
  author?: GitAuthor;
  committer?: GitAuthor;
}

export interface LogOptions {
  ref?: string;
  limit?: number;
  offset?: number;
}

export interface RepoSummary {
  name: RepoName;
  status: "ready" | "importing" | "forking";
}

export interface ArtifactsPushedEvent {
  type: "cf.artifacts.repo.pushed";
  source: {
    type: "artifacts.repo";
    namespace: string;
    repoName: RepoName;
  };
  payload: {
    ref: string;
    before: string;
    after: string;
    commits: {
      id: string;
      message: string;
      messageTruncated: boolean;
      timestamp: string;
      author?: GitAuthor;
      committer?: GitAuthor;
      parents: string[];
    }[];
    totalCommitsCount: number;
    commitsTruncated: boolean;
  };
  metadata: {
    accountId: string;
    eventSubscriptionId: string;
    eventSchemaVersion: number;
    eventTimestamp: string;
  };
}

export function parseArtifactsPushedEvent(body: unknown): ArtifactsPushedEvent {
  if (typeof body !== "object" || body === null) {
    throw new Error("event body must be an object");
  }
  const candidate = body as Partial<ArtifactsPushedEvent> & { payload?: Partial<ArtifactsPushedEvent["payload"]> };
  if (candidate.type !== "cf.artifacts.repo.pushed") {
    throw new Error(`unsupported event type: ${String(candidate.type)}`);
  }
  const source = candidate.source;
  const payload = candidate.payload;
  if (!source || source.type !== "artifacts.repo" || typeof source.repoName !== "string") {
    throw new Error("missing artifacts.repo source");
  }
  if (!payload || typeof payload.ref !== "string" || typeof payload.after !== "string") {
    throw new Error("pushed payload requires ref and after");
  }
  return candidate as ArtifactsPushedEvent;
}

export interface ArtifactsPort {
  createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult>;

  fork(source: RepoName, target: RepoName, opts?: ForkOptions): Promise<ForkResult>;

  mintToken(
    repo: RepoName,
    scope?: TokenScope,
    ttlSeconds?: number,
  ): Promise<ArtifactsTokenResult>;

  log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]>;

  /**
   * Tip commit id of a ref (default HEAD). Derived ONLY from the documented
   * `log({ ref, limit: 1 })` operation — there is no documented binding API
   * that enumerates refs (codex C-1305 #2), so the port deliberately does
   * not offer ref enumeration; ref state must be tracked from push events.
   */
  headCommit(repo: RepoName, ref?: string): Promise<string | null>;

  hasCommit(repo: RepoName, sha: string): Promise<boolean>;

  listRepos(limit?: number): Promise<RepoSummary[]>;

  deleteRepo(name: RepoName): Promise<boolean>;
}
