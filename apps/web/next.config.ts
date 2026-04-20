import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Le frontend ne doit jamais exposer de détails Cloudflare
  // Toutes les requêtes vers les ressources passent par l'API FastAPI
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
