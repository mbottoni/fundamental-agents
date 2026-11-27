/** @type {import('next').NextConfig} */
const nextConfig = {
  // A self-contained server in .next/standalone: the production image copies
  // that and the static files, not node_modules.
  output: 'standalone',
};

module.exports = nextConfig;
