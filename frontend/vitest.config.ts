import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
    dir: "./",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
      "@brain-graph-ui": path.resolve(__dirname, "../shared/brain-graph-ui"),
      "react-force-graph-2d": path.resolve(__dirname, "node_modules/react-force-graph-2d"),
      react: path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
    },
  },
  server: {
    fs: {
      allow: [path.resolve(__dirname, "..")],
    },
  },
});

