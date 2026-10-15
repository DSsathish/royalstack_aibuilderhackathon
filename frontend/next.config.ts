import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",          // static site for Firebase Hosting; every page is a client component
  trailingSlash: true,       // /shop/ -> /shop/index.html
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
