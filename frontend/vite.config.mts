import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from '@tailwindcss/vite'
import path from "path";

export default defineConfig({
  base: "./",
  plugins: [
      vue(),
    tailwindcss()
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  css: {
    devSourcemap: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
