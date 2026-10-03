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

const HEX = "0123456789abcdef";

export function fakeSha(...parts: string[]): string {
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (const part of parts.join("\u0000").split("")) {
    h1 = (h1 ^ part.charCodeAt(0)) >>> 0;
    h1 = Math.imul(h1, 0x01000193) >>> 0;
    h2 = (h2 + part.charCodeAt(0)) >>> 0;
    h2 = Math.imul(h2 ^ (h2 >>> 13), 0x85ebca6b) >>> 0;
  }
  let out = "";
  for (let i = 0; i < 40; i++) {
    const mix = Math.imul(h1 ^ (i + 1), 0x27d4eb2f) ^ Math.imul(h2 + i * 31, 0x165667b1);
    h1 = (h1 + 0x9e3779b9 + i) >>> 0;
    h2 = (h2 ^ (mix >>> 7)) >>> 0;
    out += HEX[(mix >>> ((i % 8) * 4)) & 0xf];
  }
  return out;
}

interface FakeToken {
  id: string;
  scope: TokenScope;
  expiresAt: string;
  plaintext: string;
}

interface FakeRepo {
  name: RepoName;
  description: string;
  defaultBranch: string;
  readOnly: boolean;
  createdAt: string;
  refs: Map<string, string>;
  commits: Map<string, CommitMetadata>;
  tokens: FakeToken[];
}

export interface LocalCommitInput {
  message: string;
  parents?: string[];
  timestamp?: string;
}

export class LocalArtifacts implements ArtifactsPort {
  readonly namespace: string;
  private readonly repos = new Map<RepoName, FakeRepo>();
  private readonly trustExternalHeads: boolean;
  private tokenSeq = 0;

  constructor(namespace = "local", opts?: { trustExternalHeads?: boolean }) {
    this.namespace = namespace;
    this.trustExternalHeads = opts?.trustExternalHeads ?? true;
  }

  remoteFor(name: RepoName): string {
    return `https://local.artifacts-stub.test/git/${this.namespace}/${name}.git`;
  }

  async createRepo(name: RepoName, opts?: CreateRepoOptions): Promise<ArtifactsCreateRepoResult> {
    if (this.repos.has(name)) {
      throw new Error(`repo already exists: ${name}`);
    }
    const repo: FakeRepo = {
      name,
      description: opts?.description ?? "",
      defaultBranch: opts?.setDefaultBranch ?? "main",
      readOnly: opts?.readOnly ?? false,
      createdAt: new Date().toISOString(),
      refs: new Map(),
      commits: new Map(),
      tokens: [],
    };
    this.repos.set(name, repo);
    const token = this.mintTokenFor(repo, "write", 3600);
    return {
      name: repo.name,
      remote: this.remoteFor(name),
      defaultBranch: repo.defaultBranch,
      token: token.plaintext,
    };
  }

  async fork(source: RepoName, target: RepoName, opts?: ForkOptions): Promise<ArtifactsCreateRepoResult> {
    const src = this.mustGet(source);
    if (this.repos.has(target)) {
      throw new Error(`repo already exists: ${target}`);
    }
    if (opts?.baseSha && !src.commits.has(opts.baseSha)) {
      throw new Error(`fork base ${opts.baseSha} not found in ${source}`);
    }
    const repo: FakeRepo = {
      name: target,
      description: opts?.description ?? `Fork of ${source}`,
      defaultBranch: src.defaultBranch,
      readOnly: opts?.readOnly ?? false,
      createdAt: new Date().toISOString(),
      refs: new Map(src.refs),
      commits: new Map(src.commits),
      tokens: [],
    };
    if (opts?.baseSha) {
      repo.refs.set(`refs/heads/${repo.defaultBranch}`, opts.baseSha);
    }
    this.repos.set(target, repo);
    const token = this.mintTokenFor(repo, "write", 3600);
    return {
      name: repo.name,
      remote: this.remoteFor(target),
      defaultBranch: repo.defaultBranch,
      token: token.plaintext,
    };
  }

  async mintToken(
    repo: RepoName,
    scope: TokenScope = "write",
    ttlSeconds = 3600,
  ): Promise<ArtifactsTokenResult> {
    const target = this.mustGet(repo);
    return this.mintTokenFor(target, scope, ttlSeconds);
  }

  async log(repo: RepoName, opts?: LogOptions): Promise<CommitMetadata[]> {
    const target = this.mustGet(repo);
    const ref = opts?.ref ?? "HEAD";
    const limit = opts?.limit ?? 50;
    const offset = opts?.offset ?? 0;
    const sha = this.resolveRef(target, ref);
    if (!sha) {
      return [];
    }
    const chain: CommitMetadata[] = [];
    let cursor: string | undefined = sha;
    while (cursor && chain.length < limit + offset) {
      const commit = target.commits.get(cursor);
      if (!commit) {
        break;
      }
      chain.push(commit);
      cursor = commit.parents[0];
    }
    return chain.slice(offset, offset + limit);
  }

  async headCommit(repo: RepoName, ref = "HEAD"): Promise<string | null> {
    const target = this.mustGet(repo);
    return this.resolveRef(target, ref) ?? null;
  }

  async hasCommit(repo: RepoName, sha: string): Promise<boolean> {
    if (this.trustExternalHeads) {
      return true;
    }
    const target = this.repos.get(repo);
    return target?.commits.has(sha) ?? false;
  }

  async listRepos(limit = 100): Promise<RepoSummary[]> {
    return [...this.repos.values()].slice(0, limit).map((repo) => ({
      name: repo.name,
      status: "ready" as const,
    }));
  }

  async deleteRepo(name: RepoName): Promise<boolean> {
    return this.repos.delete(name);
  }

  async applyPush(repo: RepoName, ref: string, commit: LocalCommitInput): Promise<CommitMetadata> {
    const target = this.mustGet(repo);
    const parents = commit.parents ?? (this.resolveRef(target, ref) ? [this.resolveRef(target, ref)!] : []);
    const created: CommitMetadata = {
      id: fakeSha(repo, ref, commit.message, commit.timestamp ?? "", parents.join(","), String(target.commits.size)),
      message: commit.message,
      timestamp: commit.timestamp ?? new Date().toISOString(),
      parents,
      author: { name: "local-stub", email: "stub@artifacts-stub.test" },
      committer: { name: "local-stub", email: "stub@artifacts-stub.test" },
    };
    target.commits.set(created.id, created);
    target.refs.set(ref, created.id);
    return created;
  }

  private resolveRef(repo: FakeRepo, ref: string): string | undefined {
    if (ref === "HEAD") {
      return repo.refs.get(`refs/heads/${repo.defaultBranch}`);
    }
    return repo.refs.get(ref.startsWith("refs/") ? ref : `refs/heads/${ref}`);
  }

  private mustGet(name: RepoName): FakeRepo {
    const repo = this.repos.get(name);
    if (!repo) {
      throw new Error(`repo not found: ${name}`);
    }
    return repo;
  }

  private mintTokenFor(repo: FakeRepo, scope: TokenScope, ttlSeconds: number): FakeToken {
    this.tokenSeq += 1;
    const expiresUnix = Math.floor(Date.now() / 1000) + ttlSeconds;
    const secret = fakeSha("token", repo.name, scope, String(this.tokenSeq), String(expiresUnix));
    const token: FakeToken = {
      id: fakeSha("token-id", secret).slice(0, 16),
      scope,
      expiresAt: new Date(expiresUnix * 1000).toISOString(),
      plaintext: `art_v1_${secret}?expires=${expiresUnix}`,
    };
    repo.tokens.push(token);
    return token;
  }
}
