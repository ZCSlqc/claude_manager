import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/static': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/continue': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/heartbeat': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/users': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
      '/projects': {
        target: 'http://localhost:8112',
        changeOrigin: true,
      },
    },
  },
})
