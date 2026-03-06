import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/static/dist/', // هذا يحل مشكلة MIME type
  plugins: [vue()],
  build: {
    outDir: 'static/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      }
    }
  }
})