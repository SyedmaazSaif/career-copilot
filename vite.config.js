import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" so the packaged app can load assets from a file:// URL later.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
  },
});
