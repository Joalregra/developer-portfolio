import { defineConfig } from '@playwright/test'

const PORT = 4173

// Layout tests run against the production build (`npm run build` first), served by `vite preview`.
// Locally, PW_CHANNEL=msedge (or chrome) reuses an installed browser instead of downloading one.
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    channel: process.env.PW_CHANNEL || undefined,
    // The checks measure where things end up. The assistant panel scales in, so on a slow
    // runner a measure taken while it opens is a few pixels off; the app turns motion off
    // under this setting, so the box is final as soon as it appears.
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npm run preview -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}/es/`,
    reuseExistingServer: !process.env.CI,
  },
})
