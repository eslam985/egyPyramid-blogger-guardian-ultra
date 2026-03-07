import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite' // 1. أضف هذا الاستيراد

export default defineConfig({
  base: '/static/dist/',
  plugins: [
    vue(),
    tailwindcss(), // 2. أضف الإضافة هنا
  ],
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