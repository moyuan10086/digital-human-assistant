import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: '/', // Ensure absolute paths for assets
  server: {
    proxy: {
      '/api': 'http://localhost:8004',
      '/chat': 'http://localhost:8004',
      '/history': 'http://localhost:8004',
      '/animate': 'http://localhost:8004',
      '/tts': 'http://localhost:8004',
      '/avatars': 'http://localhost:8004',
      '/upload_avatar': 'http://localhost:8004',
      '/upload_user_avatar': 'http://localhost:8004',
      '/upload_ai_avatar': 'http://localhost:8004',
      '/config': 'http://localhost:8004',
      '/ws': {
        target: 'ws://localhost:8004',
        ws: true
      }
    }
  }
})
