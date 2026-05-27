import type { NextConfig } from "next";

const internalApiBaseUrl = (process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
