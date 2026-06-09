/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || (
  process.env.NODE_ENV === 'production' ? '' : 'http://127.0.0.1:8001'
);

if (!BACKEND_URL) {
  throw new Error('BACKEND_URL must be set for production builds/deployments.');
}

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
  // V5.17.1 — Bump Next.js dev proxy timeout from default 30s → 180s.
  // /storyboard/master needs ~60-90s for Seedream v4.5 ultra-wide gen.
  // /director/plan can take ~60-120s with Director + Vision + Evaluation LLMs.
  // Without this, FE sees "socket hang up" ECONNRESET while BE still working
  // → user gets failure UI even though BE completes + charges $0.04.
  experimental: {
    proxyTimeout: 180000,
  },
};

module.exports = nextConfig;
