/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { localeHead } from './vite-plugin-locale-head.ts'

const page = (path: string) => fileURLToPath(new URL(path, import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const siteUrl = env.VITE_SITE_URL?.replace(/\/$/, '') || undefined

  return {
    plugins: [react(), tailwindcss(), localeHead(siteUrl)],
    define: {
      // "Last updated" in the footer: the month of the build.
      __BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 7)),
    },
    build: {
      rollupOptions: {
        // One entry per language (/es/ and /en/) plus the root, which picks a language.
        input: {
          main: page('./index.html'),
          es: page('./es/index.html'),
          en: page('./en/index.html'),
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
