/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The GasWise service token must never reach the browser bundle. The dev proxy
// reads it server-side (frontend/.env.local, then backend/.env) and injects it.
function backendToken(env: Record<string, string>): string {
  if (env.GASWISE_API_TOKEN) return env.GASWISE_API_TOKEN
  try {
    const line = readFileSync(resolve(import.meta.dirname, '../backend/.env'), 'utf8')
      .split('\n')
      .find((row) => row.startsWith('GASWISE_API_TOKEN='))
    return line?.slice('GASWISE_API_TOKEN='.length).trim().replace(/^["']|["']$/g, '') ?? ''
  } catch {
    return ''
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, '')
  const token = backendToken(env)
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': {
          target: env.GASWISE_API_URL || 'http://127.0.0.1:8000',
          rewrite: (path) => path.replace(/^\/api/, ''),
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        },
      },
    },
    test: {
      include: ['src/**/*.test.{ts,tsx}'],
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
    },
  }
})
