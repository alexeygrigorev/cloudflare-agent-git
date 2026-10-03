import { describe, expect, it } from "vitest";
import { LocalArtifacts, fakeSha } from "../src/artifacts/local.js";
import type { ArtifactsPushedEvent } from "../src/types.js";
import { parseArtifactsPushedEvent } from "../src/types.js";

describe("LocalArtifacts (in-memory fake)", () => {
  it("creates repos with documented remote + token format", async () => {
    const port = new LocalArtifacts("ns1");
    const created = await port.createRepo("baseline", { setDefaultBranch: "main" });
    expect(created.name).toBe("baseline");
    expect(created.remote).toBe("https://local.artifacts-stub.test/git/ns1/baseline.git");
    expect(created.defaultBranch).toBe("main");
    expect(created.token).toMatch(/^art_v1_[0-9a-f]{40}\?expires=\d+$/);
  });

  it("rejects duplicate repo names", async () => {
    const port = new LocalArtifacts("ns1");
    await port.createRepo("dup");
    await expect(port.createRepo("dup")).rejects.toThrow("repo already exists");
  });

  it("records pushes and walks first-parent history newest-first", async () => {
    const port = new LocalArtifacts("ns1");
    await port.createRepo("hist");
    const c1 = await port.applyPush("hist", "refs/heads/main", { message: "one" });
    const c2 = await port.applyPush("hist", "refs/heads/main", { message: "two" });
    const log = await port.log("hist", { ref: "refs/heads/main" });
    expect(log.map((c) => c.id)).toEqual([c2.id, c1.id]);
    expect(log[0].parents).toEqual([c1.id]);
    expect(await port.headCommit("hist")).toBe(c2.id);
    expect(await port.headCommit("hist", "refs/heads/main")).toBe(c2.id);
  });

  it("headCommit returns null for unknown refs (no ref enumeration on the port)", async () => {
    const port = new LocalArtifacts("ns1");
    await port.createRepo("fresh");
    expect(await port.headCommit("fresh")).toBeNull();
    expect(await port.headCommit("fresh", "refs/heads/nope")).toBeNull();
  });

  it("returns empty log for unknown refs", async () => {
    const port = new LocalArtifacts("ns1");
    await port.createRepo("empty");
    expect(await port.log("empty", { ref: "refs/heads/nope" })).toEqual([]);
  });

  it("forks copy history and mint scoped tokens per repo", async () => {
    const port = new LocalArtifacts("ns1");
    await port.createRepo("base");
    await port.applyPush("base", "refs/heads/main", { message: "seed" });
    const forked = await port.fork("base", "base-copy", { defaultBranchOnly: true });
    expect(forked.name).toBe("base-copy");
    expect(forked.remote).toBe("https://local.artifacts-stub.test/git/ns1/base-copy.git");
    const forkLog = await port.log("base-copy", {});
    expect(forkLog.map((c) => c.message)).toEqual(["seed"]);
    const read = await port.mintToken("base-copy", "read", 900);
    expect(read.scope).toBe("read");
    expect(read.plaintext).not.toBe(forked.token);
    expect(read.expiresAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("trusts or rejects external heads depending on configuration", async () => {
    const trusting = new LocalArtifacts("ns1");
    await trusting.createRepo("r");
    expect(await trusting.hasCommit("r", "0".repeat(40))).toBe(true);
    const strict = new LocalArtifacts("ns1", { trustExternalHeads: false });
    await strict.createRepo("r");
    const commit = await strict.applyPush("r", "refs/heads/main", { message: "real" });
    expect(await strict.hasCommit("r", commit.id)).toBe(true);
    expect(await strict.hasCommit("r", "0".repeat(40))).toBe(false);
  });

  it("lists and deletes repos", async () => {
    const port = new LocalArtifacts("ns1");
    await port.createRepo("keep");
    await port.createRepo("drop");
    expect((await port.listRepos()).map((r) => r.name)).toEqual(["keep", "drop"]);
    expect(await port.deleteRepo("drop")).toBe(true);
    expect((await port.listRepos()).map((r) => r.name)).toEqual(["keep"]);
  });

  it("fakeSha is deterministic 40-hex and input-sensitive", () => {
    const a = fakeSha("x", "y");
    expect(a).toMatch(/^[0-9a-f]{40}$/);
    expect(a).toBe(fakeSha("x", "y"));
    expect(a).not.toBe(fakeSha("x", "z"));
  });
});

describe("push event envelope", () => {
  const event: ArtifactsPushedEvent = {
    type: "cf.artifacts.repo.pushed",
    source: { type: "artifacts.repo", namespace: "ns", repoName: "some-fork" },
    payload: {
      ref: "refs/heads/main",
      before: "b".repeat(40),
      after: "a".repeat(40),
      commits: [
        {
          id: "a".repeat(40),
          message: "wip",
          messageTruncated: false,
          timestamp: "2026-10-03T10:00:00.000Z",
          parents: ["b".repeat(40)],
        },
      ],
      totalCommitsCount: 1,
      commitsTruncated: false,
    },
    metadata: {
      accountId: "acct",
      eventSubscriptionId: "sub",
      eventSchemaVersion: 1,
      eventTimestamp: "2026-10-03T10:00:00.132Z",
    },
  };

  it("parses a documented cf.artifacts.repo.pushed envelope", () => {
    const parsed = parseArtifactsPushedEvent(event);
    expect(parsed.payload.after).toBe("a".repeat(40));
    expect(parsed.source.repoName).toBe("some-fork");
  });

  it("rejects other event types and malformed payloads", () => {
    expect(() => parseArtifactsPushedEvent({ type: "cf.artifacts.repo.cloned" })).toThrow(
      "unsupported event type",
    );
    expect(() => parseArtifactsPushedEvent({ type: "cf.artifacts.repo.pushed", payload: {} })).toThrow();
    expect(() => parseArtifactsPushedEvent(null)).toThrow();
  });
});
