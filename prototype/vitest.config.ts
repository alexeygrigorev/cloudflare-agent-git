import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest((ctx) => ({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          // Test-only values injected into the worker under test. Real
          // deployments set these via secrets; see README (auth).
          ADMIN_TOKEN: "test-admin-token",
          RUNNER_TOKEN: "test-runner-token",
          LOCAL_ARTIFACTS_URL: ctx.inject<string>("sidecarUrl"),
          LOCAL_ARTIFACTS_TOKEN: "test-sidecar-token",
        },
      },
    })),
  ],
  test: {
    include: ["test/**/*.test.ts"],
    globalSetup: ["test/global-setup.ts"],
  },
});
