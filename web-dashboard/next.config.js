/** @type {import('next').NextConfig} */
const nextConfig = {
  /**
   * Local dev proxy: forwards /api/* → coordinator at COORDINATOR_URL.
   * In production (Vercel), the rewrite in vercel.json handles this instead.
   *
   * Set COORDINATOR_URL in web-dashboard/.env.local for local dev:
   *   COORDINATOR_URL=http://localhost:8000
   */
  async rewrites() {
    const coordinatorUrl = process.env.COORDINATOR_URL;
    if (!coordinatorUrl) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${coordinatorUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
