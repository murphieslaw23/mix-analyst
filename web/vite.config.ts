import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // The page owns registration so it can offer a clear, explicit update
      // decision instead of allowing an install to replace a live session.
      injectRegister: false,
      registerType: "prompt",
      manifest: false,
      strategies: "injectManifest",
      srcDir: "src/pwa",
      filename: "service-worker.js",
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,webmanifest}"],
      },
    }),
  ],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        // Docker's internal hostname is correct only inside the Compose
        // network. Host development explicitly targets the loopback API.
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
