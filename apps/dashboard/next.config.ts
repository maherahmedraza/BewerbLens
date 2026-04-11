import type { NextConfig } from "next";
import { config } from "dotenv";
import { resolve } from "path";

// Carga las variables NEXT_PUBLIC_* desde el .env raíz del monorepo
config({ path: resolve(__dirname, "../../.env") });

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
