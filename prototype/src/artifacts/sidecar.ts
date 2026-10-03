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

/**
 * ArtifactsPort backed by the local git sidecar (live/sidecar.mjs): real bare
 * git repositories served over smart HTTP, so forks are genuinely clonable and
 * pushable with plain git. Selected when env.ARTIFACTS_IMPL === "sidecar".
 */
export class SidecarArtifacts implements ArtifactsPort {
  private readonly baseUrl: string;
  private readonly adminToken: string;

  constructor(baseUrl: string, adminToken = "") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.adminToken = adminToken;
  }

  private async call<T>(path: string, init?: RequestInit): Promise<T> {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (this.adminToken) {
      headers.authorization = `Bearer ${this.adminToken}`;
    }
    const res = await fetch(`${this.baseUrl}${path}`, { ...init, headers: { ...headers, ...init?.headers } });
    const body = (await res.json()) as T & { error?: string };
    if (!res.ok) {
      throw new Error(body?.error ?? `sidecar ${init?.method ?? "GET"} ${path} failed: HTTP ${res.status}`);
    }
    return body;
  }

  async createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult> {
    return this.call("/api/repos", {
      method: "POST",
      body: JSON.stringify({ name, setDefaultBranch: opts?.setDefaultBranch }),
    });
  }

  async fork(source: RepoName, target: RepoName, _opts?: ForkOptions): Promise<ArtifactsCreateRepoResult> {
    return this.call(`/api/repos/${encodeURIComponent(source)}/fork`, {
      method: "POST",
      body: JSON.stringify({ target }),
    });
  }

  async mintToken(repo: RepoName, scope: TokenScope = "write", ttlSeconds = 3600): Promise<ArtifactsTokenResult> {
    return this.call(`/api/repos/${encodeURIComponent(repo)}/tokens`, {
      method: "POST",
      body: JSON.stringify({ scope, ttlSeconds }),
    });
  }

  async log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]> {
    const params = new URLSearchParams();
    if (opts?.ref) params.set("ref", opts.ref);
    if (opts?.limit) params.set("limit", String(opts.limit));
    return this.call(`/api/repos/${encodeURIComponent(repo)}/log?${params}`);
  }

  async listRefs(repo: RepoName): Promise<Record<string, string>> {
    return this.call(`/api/repos/${encodeURIComponent(repo)}/refs`);
  }

  async hasCommit(repo: RepoName, sha: string): Promise<boolean> {
    const body = await this.call<{ exists: boolean }>(
      `/api/repos/${encodeURIComponent(repo)}/has-commit/${sha}`,
    );
    return body.exists;
  }

  async listRepos(limit = 100): Promise<RepoSummary[]> {
    const body = await this.call<{ repos: RepoSummary[] }>("/api/repos");
    return body.repos.slice(0, limit);
  }

  async deleteRepo(name: RepoName): Promise<boolean> {
    const body = await this.call<{ deleted: boolean }>(`/api/repos/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
    return body.deleted;
  }
}
