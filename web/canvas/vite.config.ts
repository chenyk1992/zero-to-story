import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4178,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        configure: (proxy) => {
          const eventProxy = proxy as unknown as {
            on: (event: 'proxyReq', listener: (request: { setHeader: (name: string, value: string) => void }) => void) => void;
          };
          eventProxy.on('proxyReq', (proxyRequest) => {
            // The local canvas service validates both Host and Origin. The
            // browser remains same-origin with Vite while the proxy presents
            // the loopback service origin upstream.
            proxyRequest.setHeader('Origin', 'http://127.0.0.1:8765');
          });
        },
      },
    },
  },
  build: {
    target: 'es2022',
  },
});
