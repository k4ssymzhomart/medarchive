import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// MedPartners frontend dev config.
// Proxy /api -> backend at :8000, stripping the /api prefix.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
