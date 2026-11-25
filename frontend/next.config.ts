import type { NextConfig } from "next";

// All API calls go to /api/* on the same origin.
// - On Vercel, /api/* is served by the Python function in api/index.py.
// - In local dev, Next.js proxies /api/* to the Flask server (npm run dev).
const API_DEV_URL = process.env.API_DEV_URL ?? "http://127.0.0.1:5001";

const nextConfig: NextConfig = {
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [{ source: "/api/:path*", destination: `${API_DEV_URL}/api/:path*` }]
      : [{ source: "/api/:path*", destination: "/api/" }];
  },
};

export default nextConfig;
