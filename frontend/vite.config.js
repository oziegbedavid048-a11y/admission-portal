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
    // No hand-made chunk rules. Each page, Chart.js and pdf.js are loaded
    // with a dynamic import, so the bundler splits them and the first page
    // downloads only what it shows. Forcing every package into one "vendor"
    // chunk made the landing page download the charts and the PDF reader.
  },
});
