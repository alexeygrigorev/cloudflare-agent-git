import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest((ctx) => ({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          // Test-only values injected into the worker under test. Real
          // deployments set these via secrets; see README (auth) and DEPLOY.md.
          ADMIN_TOKEN: "test-admin-token",
          RUNNER_TOKEN: "test-runner-token",
          LOCAL_ARTIFACTS_URL: ctx.inject<string>("sidecarUrl"),
          LOCAL_ARTIFACTS_TOKEN: "test-sidecar-token",
          // §5.7 CORS tests exercise the allowlist path; "closed by default"
          // (unset var) is covered by unit tests on corsPolicyFromEnv.
          ALLOWED_ORIGINS: "https://dashboard.example,https://preview.example",
        },
      },
    })),
  ],
  test: {
    include: ["test/**/*.test.ts"],
    globalSetup: ["test/global-setup.ts"],
    // Real-git sidecar round trips (commit/push per request) are slow under
    // full-suite concurrency; 30s per test avoids flaky timeouts.
    testTimeout: 30_000,
    // Each test file spawns its own workerd while the shared real-git sidecar
    // does real git work per request; parallel files OOM-kill the 1.5 GiB
    // executor sandbox, so files run sequentially (observed by zc-l1-fix).
    fileParallelism: false,
  },
});
