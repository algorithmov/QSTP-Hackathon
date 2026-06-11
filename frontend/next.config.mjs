/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-simple-maps uses topojson/d3 with browser-only APIs; suppress SSR warnings
  webpack(config) {
    return config;
  },
};

export default nextConfig;
