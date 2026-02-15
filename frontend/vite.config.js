import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  optimizeDeps: {
    include: ['vue', 'vue-router', 'lucide-vue-next'],
  },
  server: {
    fs: {
      // Allow reading common_site_config.json from sites/ (for socketio_port)
      allow: [path.resolve(__dirname, '..'), path.resolve(__dirname, '../../../sites')],
    },
  },
  build: {
    outDir: '../ai_chatbot/public/frontend',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
      },
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router'],
          'markdown': ['marked', 'highlight.js'],
          'icons': ['lucide-vue-next'],
          'echarts': ['echarts'],
        },
      },
    },
  },
})
