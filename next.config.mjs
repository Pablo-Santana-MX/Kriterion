/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Desarrollo local: `next dev` (3000) reenvía /api/* a uvicorn (8000).
  // En Vercel no se usa: vercel.json enruta /api/* a la función Python.
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return [];
    return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }];
  },
};

export default nextConfig;
