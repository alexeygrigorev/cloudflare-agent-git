import { RealArtifacts } from "../artifacts/real.js";
import { SidecarArtifacts } from "../local/githost.js";
import type { GitHost } from "../ports/githost.js";

export { RealArtifacts, type ArtifactsNamespaceBinding } from "../artifacts/real.js";

export function gitHostFromEnv(env: Env, realArtifactsOpts?: any): GitHost {
  if (env.ARTIFACTS) {
    return new RealArtifacts(env.ARTIFACTS, realArtifactsOpts);
  }
  if (env.LOCAL_ARTIFACTS_URL) {
    return new SidecarArtifacts(env.LOCAL_ARTIFACTS_URL, env.LOCAL_ARTIFACTS_TOKEN);
  }
  throw new Error(
    "no Artifacts backend configured: set the ARTIFACTS binding (real) or LOCAL_ARTIFACTS_URL (local sidecar)",
  );
}
