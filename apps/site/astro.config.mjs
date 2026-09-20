// apps/site/astro.config.mjs
// The project site: Astro with React islands, built by the pinned bun.
//
// STATIC OUTPUT. Every "retrieve as data" section reads evidence that is
// committed in this repository -- .artifacts/runs/*.json carries a versioned
// run-record/v1 contract, .artifacts/repo-settings/*.json a verdict. Reading
// committed files at build time needs no server, and a malformed record fails
// the build instead of rendering broken in production.
import { defineConfig } from "astro/config";
import react from "@astrojs/react";

export default defineConfig({
  output: "static",
  integrations: [react()],
  server: { port: 4321 },
});
