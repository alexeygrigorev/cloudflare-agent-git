import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startSidecar } from "../local-artifacts/sidecar.mjs";

interface GlobalSetupContext {
  provide(key: string, value: unknown): void;
}

/**
 * Boots the local Artifacts sidecar (real bare git repos on disk) once for
 * the whole vitest run; the worker under test reaches it over outbound
 * fetch via the LOCAL_ARTIFACTS_URL binding injected in vitest.config.ts.
 */
export default async function setup(vitest: GlobalSetupContext): Promise<() => Promise<void>> {
  const resources: { root: string; handle: Awaited<ReturnType<typeof startSidecar>> | null }[] = [];
  const close = async () => {
    for (const { root, handle } of [...resources].reverse()) {
      if (handle) await handle.close();
      // Every path was created by this setup invocation, never discovered.
      rmSync(root, { recursive: true, force: true });
    }
  };
  try {
    for (const [label, key] of [["general", "sidecarUrl"], ["budget", "budgetSidecarUrl"]]) {
      const resource = { root: mkdtempSync(join(tmpdir(), `agent-branches-sidecar-vitest-${label}-`)), handle: null as Awaited<ReturnType<typeof startSidecar>> | null };
      resources.push(resource);
      resource.handle = await startSidecar({
        root: resource.root, host: "127.0.0.1", port: 0,
        token: "test-sidecar-token", notifyUrl: null,
      });
      vitest.provide(key, `http://127.0.0.1:${resource.handle.port}`);
      console.error(`[global-setup] ${label} sidecar on port ${resource.handle.port}`);
    }
  } catch (error) {
    await close();
    throw error;
  }
  vitest.provide("sidecarToken", "test-sidecar-token");
  return close;
}
