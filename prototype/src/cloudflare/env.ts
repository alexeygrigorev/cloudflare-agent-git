/**
 * Cloudflare env typings (facade extraction, 2026-10-03) — moved verbatim
 * from the pre-facade src/index.ts.
 */

import type { ArtifactsNamespaceBinding } from "../artifacts/real.js";
import type { Coordinator } from "./coordinator-do.js";

declare global {
  interface Env {
    ARTIFACTS?: ArtifactsNamespaceBinding;
    RADAR_IMPL?: string;
    ADMIN_TOKEN?: string;
    RUNNER_TOKEN?: string;
    LOCAL_ARTIFACTS_URL?: string;
    LOCAL_ARTIFACTS_TOKEN?: string;
    MAX_DAILY_OPS?: number | string;
    MAX_MONTHLY_OPS?: number | string;
    MAX_REPOS?: number | string;
    MAX_TOTAL_BYTES?: number | string;
    MAX_BODY_BYTES?: number | string;
    BUDGET_MAX_DAILY_OPS?: number | string;
    BUDGET_MAX_MONTHLY_OPS?: number | string;
    BUDGET_MAX_REPOS?: number | string;
    BUDGET_MAX_TOTAL_BYTES?: number | string;
    BUDGET_MAX_BODY_BYTES?: number | string;
    ENFORCE_CLOUD_BUDGET?: boolean | string;
  }
}

declare module "cloudflare:workers" {
  namespace Cloudflare {
    interface Env {
      COORDINATOR: DurableObjectNamespace<Coordinator>;
      ARTIFACTS?: ArtifactsNamespaceBinding;
      RADAR_IMPL?: string;
      ADMIN_TOKEN?: string;
      RUNNER_TOKEN?: string;
      LOCAL_ARTIFACTS_URL?: string;
      LOCAL_ARTIFACTS_TOKEN?: string;
      MAX_DAILY_OPS?: number | string;
      MAX_MONTHLY_OPS?: number | string;
      MAX_REPOS?: number | string;
      MAX_TOTAL_BYTES?: number | string;
      MAX_BODY_BYTES?: number | string;
      BUDGET_MAX_DAILY_OPS?: number | string;
      BUDGET_MAX_MONTHLY_OPS?: number | string;
      BUDGET_MAX_REPOS?: number | string;
      BUDGET_MAX_TOTAL_BYTES?: number | string;
      BUDGET_MAX_BODY_BYTES?: number | string;
      ENFORCE_CLOUD_BUDGET?: boolean | string;
    }
  }
}
