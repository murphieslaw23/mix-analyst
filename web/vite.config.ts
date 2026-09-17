import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // The update applies only after the user accepts it in UpdateBanner;
      // never skipWaiting on install.
      registerType: "prompt",
      includeAssets: [
        "icon.svg",
        "icon-192.png",
        "icon-512.png",
        "icon-maskable-512.png",
        "apple-touch-icon.png",
      ],
      manifest: false, // hand-authored manifest.webmanifest stays canonical
      workbox: {
        // App-shell fallback for navigations only. Operational traffic
        // (/api/*, uploads, streams, downloads) is network-only: no cached
        // API response may ever impersonate the backend.
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/uploads\//, /^\/downloads\//],
        runtimeCaching: [],
        // Push/click handlers live in a follow-up injectManifest worker;
        // generateSW must not claim clients out from under the user.
        skipWaiting: false,
        clientsClaim: false,
      },
      devOptions: {
        // Service workers stay disabled under `vite dev` so E2E and local
        // development never execute precache logic by accident.
        enabled: false,
      },
    }),
  ],
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
