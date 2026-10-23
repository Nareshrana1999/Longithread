/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Proxy API calls to the FastAPI backend during local development.
    return [{ source: "/api/:path*", destination: "http://localhost:8000/:path*" }];
  },
};
export default nextConfig;
