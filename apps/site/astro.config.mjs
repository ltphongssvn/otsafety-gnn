// apps/site/astro.config.mjs
// The project site: Astro, built by the pinned bun.
//
// NO FRAMEWORK INTEGRATION. React was registered here and declared in
// package.json, and nothing rendered with it: no .tsx file, no client:
// directive. Its integration pulled in vite:react-babel, which sets esbuild
// and optimizeDeps.esbuildOptions -- both deprecated in Vite 8 -- so every
// build warned three times for a framework the site never used.
//
// STATIC OUTPUT. Every "retrieve as data" section reads evidence that is
// committed in this repository -- .artifacts/runs/*.json carries a versioned
// run-record/v1 contract, .artifacts/repo-settings/*.json a verdict. Reading
// committed files at build time needs no server, and a malformed record fails
// the build instead of rendering broken in production.
import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  server: { port: 4321 },
});
