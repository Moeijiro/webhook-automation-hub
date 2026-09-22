import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// /api/ and /hooks/ are proxied to the backend so the dashboard and the API
// share an origin in development, exactly as they would behind one domain.
// The keys are regexes on purpose: a plain "/api" prefix would also swallow
// client-side routes such as /api-keys.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    proxy: {
      "^/api/": { target: process.env.VITE_API_TARGET ?? "http://localhost:8000" },
      "^/hooks/": { target: process.env.VITE_API_TARGET ?? "http://localhost:8000" },
    },
  },
});
