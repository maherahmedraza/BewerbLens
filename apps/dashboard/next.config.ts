import type { NextConfig } from "next";

// ── Dual-mode env loading ────────────────────────────────────────
// Local dev: loads from root .env via dotenv (Next.js auto-loads .env files
//            but since we're in a monorepo subfolder, we load from ../../.env)
// Vercel/CI: env vars are injected by the platform, dotenv is skipped.
if (!process.env.VERCEL && !process.env.CI) {
  try {
    const dotenv = require("dotenv");
    const path = require("path");
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  } catch {
    // dotenv may not be available in production builds — that's fine
  }
}

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
        ],
      },
    ]
  },
};

export default nextConfig;
