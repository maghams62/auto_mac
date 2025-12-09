import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    externalDir: true,
  },
  turbopack: {},
  // Ensure Turbopack and Webpack both resolve the shared brain graph UI package.
  webpack: (config) => {
    config.resolve.alias["@brain-graph-ui"] = path.resolve(process.cwd(), "../shared/brain-graph-ui");
    config.resolve.alias["react-force-graph-2d"] = path.resolve(process.cwd(), "node_modules/react-force-graph-2d");
    return config;
  },
};

export default nextConfig;
