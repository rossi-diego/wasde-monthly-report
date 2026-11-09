import type { NextConfig } from "next";

// Fully static site: data is pre-computed monthly by the Python pipeline into public/data.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default config;
