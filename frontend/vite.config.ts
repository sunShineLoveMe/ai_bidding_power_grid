import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

declare const process: { env?: Record<string, string | undefined> };

const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:3012';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': apiTarget,
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
