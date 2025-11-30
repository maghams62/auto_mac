const isProdBuild = process.env.NODE_ENV === 'production';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
