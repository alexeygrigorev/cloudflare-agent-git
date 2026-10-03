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

/**
 * Local-mode ArtifactsPort backed by the Node sidecar (codex C-1309 #7a):
 * real bare git repos on disk, reached over fetch. The Worker performs no
 * git operations itself — forks are `git clone --bare`, pushes happen with
 * ordinary `git push` against the sidecar's smart HTTP endpoint.
 */
export class SidecarArtifacts implements ArtifactsPort {
  private readonly baseUrl: string;
  private readonly token: string | undefined;

  constructor(baseUrl: string, token?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.token = token;
  }

  private async call(path: string, init?: RequestInit): Promise<unknown> {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (this.token) {
      headers.authorization = `Bearer ${this.token}`;
    }
    const res = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    if (!res.ok) {
      throw new Error(body.error ?? `sidecar ${path} failed: HTTP ${res.status}`);
    }
    return body;
  }

  async createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult> {
    const body = (await this.call("/api/repos", {
      method: "POST",
      body: JSON.stringify({ name, defaultBranch: opts?.setDefaultBranch }),
    })) as ArtifactsCreateRepoResult;
    return { name: body.name, remote: body.remote, defaultBranch: body.defaultBranch, token: body.token };
  }

  async fork(source: RepoName, target: RepoName, opts?: ForkOptions): Promise<ForkResult> {
    const body = (await this.call(`/api/repos/${encodeURIComponent(source)}/fork`, {
      method: "POST",
      body: JSON.stringify({ target, baseSha: opts?.baseSha }),
    })) as ArtifactsCreateRepoResult;
    // Local mode honors baseSha exactly (git update-ref after bare clone),
    // so the realized base is the requested one; no marker needed.
    return { name: body.name, remote: body.remote, defaultBranch: body.defaultBranch, token: body.token };
  }

  async mintToken(repo: RepoName, scope: TokenScope = "write", ttlSeconds = 3600): Promise<ArtifactsTokenResult> {
    return (await this.call(`/api/repos/${encodeURIComponent(repo)}/tokens`, {
      method: "POST",
      body: JSON.stringify({ scope, ttlSeconds }),
    })) as ArtifactsTokenResult;
  }

  async log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]> {
    const params = new URLSearchParams();
    params.set("ref", opts?.ref ?? "HEAD");
    params.set("limit", String(opts?.limit ?? 50));
    params.set("offset", String(opts?.offset ?? 0));
    return (await this.call(`/api/repos/${encodeURIComponent(repo)}/log?${params}`)) as CommitMetadata[];
  }

  async headCommit(repo: RepoName, ref = "HEAD"): Promise<string | null> {
    const body = (await this.call(
      `/api/repos/${encodeURIComponent(repo)}/head?ref=${encodeURIComponent(ref)}`,
    )) as { sha: string | null };
    return body.sha;
  }

  async hasCommit(repo: RepoName, sha: string): Promise<boolean> {
    const body = (await this.call(
      `/api/repos/${encodeURIComponent(repo)}/hascommit?sha=${encodeURIComponent(sha)}`,
    )) as { known: boolean };
    return body.known;
  }

  async listRepos(limit = 100): Promise<RepoSummary[]> {
    const body = (await this.call(`/api/repos?limit=${limit}`)) as { repos: RepoSummary[] };
    return body.repos.slice(0, limit);
  }

  async deleteRepo(name: RepoName): Promise<boolean> {
    const body = (await this.call(`/api/repos/${encodeURIComponent(name)}`, { method: "DELETE" })) as {
      deleted: boolean;
    };
    return body.deleted;
  }

  /** Pushes whose Worker callback failed after bounded retries (C-1357). */
  async unprocessedPushes(): Promise<UnprocessedPush[]> {
    const body = (await this.call("/api/notify-state")) as { unprocessed: UnprocessedPush[] };
    return body.unprocessed;
  }
}
