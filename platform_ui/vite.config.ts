import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, the SPA runs on :5173 and forwards API calls to the FastAPI service
// (uvicorn platform_api.main:app --port 8000). In production FastAPI serves the
// built files itself, so no proxy and no CORS are needed.
const API = "http://localhost:8000";
const apiPaths = [
  "/auth", "/status", "/config", "/data", "/transactions", "/versions", "/runs",
  "/jobs", "/pipeline", "/drift", "/models", "/services", "/health",
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(apiPaths.map((p) => [p, { target: API, changeOrigin: true }])),
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
