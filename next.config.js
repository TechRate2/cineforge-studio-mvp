/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

const nextConfig = {
  reactStrictMode: true,
  images: { remotePatterns: [{ protocol: 'https', hostname: '**' }] },
  // V3 — proxy all /api/v1/* calls from the Next.js dev server to the FastAPI
  // backend so client-side `fetch('/api/v1/...')` works without CORS hassle.
  // Production: set BACKEND_URL env (or deploy behind a single reverse proxy).
  async rewrites() {
    return [
      { source: '/api/v1/:path*', destination: `${BACKEND_URL}/api/v1/:path*` },
    ];
  },
};

module.exports = nextConfig;
