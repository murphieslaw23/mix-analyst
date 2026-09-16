import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        // Docker hostname by default; override for host-local API runs:
        // VITE_DEV_API_TARGET=http://localhost:8000 npm run dev
        target: process.env.VITE_DEV_API_TARGET || "http://api:8000",
        changeOrigin: true,
      },
    },
  },
});
