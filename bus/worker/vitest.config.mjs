import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

// Runs the worker under workerd via the same plugin the Agent Branches prototype uses.
// node_modules is a symlink into /home/alexey/git/agent-branches-l1/prototype (no installs).
export default defineConfig({
  plugins: [
    cloudflareTest(() => ({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          BUS_MACHINES: JSON.stringify({ alpha: "t-alpha", beta: "t-beta" }),
          RATE_LIMIT_PER_MINUTE: "1000",
        },
      },
    })),
  ],
  test: {
    include: ["test/**/*.test.mjs"],
  },
});
