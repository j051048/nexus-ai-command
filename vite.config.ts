import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { VitePWA } from "vite-plugin-pwa";
import { visualizer } from "rollup-plugin-visualizer";
import path from "path";

const disablePwa = process.env.VITE_DISABLE_PWA === "1";

export default defineConfig(({ mode }) => ({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
  },
  plugins: [
    react(),
    mode === "analyze" && visualizer({ open: true, gzipSize: true, filename: "stats.html" }),
    !disablePwa && VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "logo192.png", "logo512.png", "apple-touch-icon.png"],
      manifest: {
        name: "Nexus AI 智能管理平台",
        short_name: "Nexus AI",
        description: "AI 驱动的企业智能管理平台",
        theme_color: "#6366f1",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/logo192.png", sizes: "192x192", type: "image/png" },
          { src: "/logo512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" },
        ],
      },
      workbox: {
        globPatterns: ["index.html", "assets/index-*.css", "assets/vendor-react-*.js"],
        globIgnores: [
          "**/node_modules/**",
          "**/*.map",
          "**/stats.html",
          "**/assets/vendor-syntax-*.js",
          "**/assets/vendor-charts-*.js",
          "**/assets/jspdf*.js",
        ],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: /\/[^.]*$/,
            handler: "NetworkFirst",
            options: {
              cacheName: "html-cache",
              expiration: { maxEntries: 20, maxAgeSeconds: 24 * 60 * 60 },
              networkTimeoutSeconds: 3,
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/.*\/api\//,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              expiration: { maxEntries: 100, maxAgeSeconds: 5 * 60 },
              networkTimeoutSeconds: 5,
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /\.(?:js|css)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "static-assets-cache",
              expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "image-cache",
              expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /\.(?:woff|woff2|ttf|otf|eot)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "font-cache",
              expiration: { maxEntries: 30, maxAgeSeconds: 30 * 24 * 60 * 60 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/.*\.supabase\.co\/.*/,
            handler: "NetworkFirst",
            options: {
              cacheName: "supabase-cache",
              expiration: { maxEntries: 50, maxAgeSeconds: 5 * 60 },
              networkTimeoutSeconds: 5,
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    emptyOutDir: true,
    target: "es2020",
    sourcemap: false,
    minify: "esbuild",
    reportCompressedSize: false,
    chunkSizeWarningLimit: 500,
    modulePreload: {
      resolveDependencies(_url, deps) {
        const deferUntilRouteUse = [
          "vendor-jspdf-",
          "vendor-html2canvas-",
          "vendor-charts-",
          "vendor-markdown-",
          "vendor-syntax-core-",
          "vendor-syntax-styles-",
        ];
        return deps.filter((dep) => !deferUntilRouteUse.some((prefix) => dep.includes(prefix)));
      },
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;

          if (id.includes("react-syntax-highlighter/dist/esm/styles")) return "vendor-syntax-styles";
          if (id.includes("react-syntax-highlighter")) return "vendor-syntax-core";
          if (id.includes("html2canvas")) return "vendor-html2canvas";
          if (id.includes("jspdf")) return "vendor-jspdf";
          if (id.includes("@xyflow/react")) return "vendor-flow";
          if (id.includes("recharts")) return "vendor-charts";
          if (id.includes("lucide-react")) return "vendor-icons";
          if (id.includes("@supabase/supabase-js")) return "vendor-supabase";
          if (id.includes("@tanstack/react-query")) return "vendor-query";
          if (id.includes("@hello-pangea/dnd")) return "vendor-dnd";
          if (id.includes("framer-motion") || id.includes("react-joyride")) return "vendor-motion";
          if (id.includes("date-fns") || id.includes("react-day-picker")) return "vendor-date";
          if (id.includes("react-hook-form") || id.includes("@hookform/resolvers") || id.includes("zod")) {
            return "vendor-forms";
          }
          if (
            id.includes("@radix-ui/react-dialog") ||
            id.includes("@radix-ui/react-dropdown-menu") ||
            id.includes("@radix-ui/react-tooltip") ||
            id.includes("@radix-ui/react-tabs") ||
            id.includes("@radix-ui/react-popover") ||
            id.includes("@radix-ui/react-select") ||
            id.includes("@radix-ui/react-alert-dialog") ||
            id.includes("@radix-ui/react-scroll-area")
          ) {
            return "vendor-ui";
          }
          if (id.includes("react-markdown") || id.includes("remark-gfm") || id.includes("rehype-sanitize")) {
            return "vendor-markdown";
          }
          if (id.includes("react-dom") || id.includes("react-router-dom") || /node_modules[/\\]react[/\\]/.test(id)) {
            return "vendor-react";
          }

          return undefined;
        },
      },
    },
  },
}));
