import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest(() => ({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          // Test-only values injected into the worker under test. Real
          // deployments set these via secrets; see README (auth).
          ADMIN_TOKEN: "test-admin-token",
          RUNNER_TOKEN: "test-runner-token",
        },
      },
    })),
  ],
  test: {
    include: ["test/**/*.test.ts"],
  },
});
