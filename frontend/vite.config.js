import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Vite 代理配置：所有 /api 请求自动转发到 Flask（5000 端口）
    // 好处：开发时无需手写完整地址，也不会有跨域问题
    proxy: {
      '/api': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      }
    }
  }
})
