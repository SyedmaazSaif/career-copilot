import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The renderer needs its own version number to run the update check when it is
// not inside Electron (where app.getVersion() would provide it), so bake the
// one from package.json in at build time.
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

// base: "./" so the packaged app can load assets from a file:// URL later.
export default defineConfig({
  plugins: [react()],
  base: "./",
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __APP_REPO__: JSON.stringify(pkg.repository?.url?.match(/github\.com\/(.+?)(?:\.git)?$/)?.[1] ?? ""),
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
