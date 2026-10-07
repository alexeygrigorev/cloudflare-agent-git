// Ambient declarations for test/ui-auth.test.ts only (kept out of the test
// file: a `declare module` with a wildcard pattern is not allowed there).

// Vite `?raw` imports resolve to the file's text.
declare module "*?raw" {
  const src: string;
  export default src;
}

// The workers test pool provides node:module at runtime; no @types/node here.
declare module "node:module" {
  export function createRequire(path: string | URL): (id: string) => unknown;
}
