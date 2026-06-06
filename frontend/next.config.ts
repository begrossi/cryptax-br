import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path((?!auth/).*)",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
