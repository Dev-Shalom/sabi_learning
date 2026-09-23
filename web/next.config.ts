import type { NextConfig } from "next";

const config: NextConfig = {
  // One origin: /api is proxied to FastAPI so the session cookie stays
  // first-party and there is never a CORS credential dance (v2 5.3, trap 14).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.SABI_API_ORIGIN ?? "http://127.0.0.1:8020"}/api/:path*`,
      },
    ];
  },
  // The app is not the only thing that has to work. The landing page, pricing
  // and reading mode must render server-side and stay legible without
  // JavaScript, which is why those routes are server components with no
  // client boundary.
  reactStrictMode: true,
};

export default config;
