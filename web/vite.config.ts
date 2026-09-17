import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Custom worker (src/pwa/sw.ts): versioned precache plus push /
      // click handlers with safe-link validation. Updates still apply
      // only after the user accepts them in UpdateBanner.
      strategies: 'injectManifest',
      srcDir: 'src/pwa',
      filename: 'sw.ts',
      registerType: 'prompt',
      includeAssets: [
        'icon.svg',
        'icon-192.png',
        'icon-512.png',
        'icon-maskable-512.png',
        'apple-touch-icon.png',
      ],
      manifest: false, // hand-authored manifest.webmanifest stays canonical
      injectManifest: {
        // Navigation fallback is registered inside src/pwa/sw.ts
        // (NavigationRoute with an operational-path denylist).
        globPatterns: ['**/*.{js,css,html,ico,png,svg,webmanifest}'],
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
