import { describe, expect, it } from "vitest";
import type { ArtifactsRepoCapability } from "../src/artifacts/real.js";
import { RealArtifacts, type ArtifactsNamespaceBinding } from "../src/artifacts/real.js";

/**
 * muse-r46 D3: real-mode createTask must work. The documented Artifacts
 * binding (docs-notes.md) has NO fork-at-commit parameter, so
 * RealArtifacts.fork must not throw when base_sha is requested: it forks
 * the default branch and reports the realized base (the fork's head at
 * creation) so the coordinator can record the truth (ASSUMED-F).
 *
 * The fake below is shaped strictly like the documented binding: namespace
 * methods create/get/list/import/delete, disposable repo capability with
 * info/createToken/listTokens/revokeToken/fork/log/readCommit/readTree/
 * readBlob/readFile. Note `fork(target, opts)` never receives a baseSha —
 * that parameter does not exist in the binding contract.
 */

const TIP = "c".repeat(40);

function fakeCapability(forkCalls: { target: string; opts: unknown }[]): ArtifactsRepoCapability {
  return {
    info: async () => ({ name: "canonical", defaultBranch: "main", description: null, readOnly: false }),
    createToken: async () => ({ plaintext: "art_v1_" + "f".repeat(40) + "?expires=1", expiresAt: "2026-01-01", scope: "write" }),
    listTokens: async () => ({ total: 0, tokens: [] }),
    revokeToken: async () => true,
    fork: async (target, opts) => {
      forkCalls.push({ target, opts: opts ?? null });
      return { name: target, remote: `https://acct.artifacts.cloudflare.net/git/ns/${target}.git`, defaultBranch: "main", token: "t" };
    },
    log: async () => [{ id: TIP, message: "tip", timestamp: "2026-10-03T00:00:00Z", parents: [] }],
    readCommit: async () => null,
    readTree: async () => null,
    readBlob: async () => null,
    readFile: async () => null,
    [Symbol.dispose](): void {},
  };
}

function fakeBinding(capability: ArtifactsRepoCapability): ArtifactsNamespaceBinding {
  return {
    create: async () => ({ name: "canonical", remote: "https://acct.artifacts.cloudflare.net/git/ns/canonical.git", defaultBranch: "main", token: "t" }),
    get: async () => capability,
    list: async () => ({ repos: [] }),
    import: async () => ({ name: "imported", remote: "https://acct.artifacts.cloudflare.net/git/ns/imported.git", defaultBranch: "main", token: "t" }),
    delete: async () => true,
  };
}

describe("RealArtifacts.fork with a docs-shaped fake binding (muse-r46 D3)", () => {
  it("forks the default branch and records the realized base when base_sha is requested", async () => {
    const forkCalls: { target: string; opts: unknown }[] = [];
    const port = new RealArtifacts(fakeBinding(fakeCapability(forkCalls)));

    // Old, non-tip base: the binding cannot start there; this must NOT throw.
    const oldBase = "a".repeat(40);
    const result = await port.fork("canonical", "canonical-agent-0001", {
      description: "Agent Branches fork for agent-0001",
      defaultBranchOnly: true,
      baseSha: oldBase,
    });
    expect(result.name).toBe("canonical-agent-0001");
    // The fork actually starts at the source's default-branch tip...
    expect(result.baseSha).toBe(TIP);
    expect(result.baseSha).not.toBe(oldBase);
    // ...and the binding call carried no baseSha (no such binding parameter).
    expect(forkCalls).toHaveLength(1);
    expect(forkCalls[0].opts === null || !Object.hasOwn(forkCalls[0].opts as object, "baseSha")).toBe(true);
  });

  it("reports the realized base == requested base when base_sha is the tip", async () => {
    const forkCalls: { target: string; opts: unknown }[] = [];
    const port = new RealArtifacts(fakeBinding(fakeCapability(forkCalls)));

    const result = await port.fork("canonical", "canonical-agent-0002", { baseSha: TIP });
    expect(result.baseSha).toBe(TIP);
    expect(forkCalls[0].opts === null || !Object.hasOwn(forkCalls[0].opts as object, "baseSha")).toBe(true);
  });

  it("still forks without any baseSha option (plain default-branch fork)", async () => {
    const forkCalls: { target: string; opts: unknown }[] = [];
    const port = new RealArtifacts(fakeBinding(fakeCapability(forkCalls)));

    const result = await port.fork("canonical", "canonical-agent-0003", { defaultBranchOnly: true });
    expect(result.name).toBe("canonical-agent-0003");
    expect(forkCalls[0].opts).toEqual({ defaultBranchOnly: true });
  });
});
