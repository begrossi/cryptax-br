import type { NextConfig } from "next";

// Backend proxying is handled by the catch-all Route Handler at
// src/app/api/[...path]/route.ts so we can enforce the session and inject the
// backend API token server-side (a rewrite cannot add request headers).
const nextConfig: NextConfig = {};

export default nextConfig;
