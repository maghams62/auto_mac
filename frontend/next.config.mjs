import path from 'path';

const isProdBuild = process.env.NODE_ENV === 'production';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    externalDir: true,
  },
  turbopack: {},
  webpack(config) {
    config.resolve.alias['@brain-graph-ui'] = path.resolve(process.cwd(), '../shared/brain-graph-ui');
    config.resolve.alias['react-force-graph-2d'] = path.resolve(process.cwd(), 'node_modules/react-force-graph-2d');
    return config;
  },
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  ...(isProdBuild
    ? {
        output: 'export',
        distDir: 'out',
      }
    : {}),
};

export default nextConfig;
