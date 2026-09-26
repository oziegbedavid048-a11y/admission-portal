import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The dev server proxies /api and /media to Django, so the browser sees one
    // origin and nothing depends on CORS while developing.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/media': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Charts are only reached inside the portals; keeping them in their own
        // chunk means the landing page never downloads Chart.js.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('chart.js') || id.includes('react-chartjs-2')) return 'charts';
          return 'vendor';
        },
      },
    },
  },
});
