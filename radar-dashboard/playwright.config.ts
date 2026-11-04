import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

// The E2E run owns its whole stack: a throwaway SQLite database seeded with a
// fixed dataset, its own radar-api instance and a production build of the
// dashboard. It never touches the real radar.db, .env or the running services.
const API_PORT = 8020
const DASHBOARD_PORT = 4180
export const E2E_API_KEY = 'e2e-test-key'
const DB_PATH = fileURLToPath(new URL('./e2e/.data/e2e.db', import.meta.url))

export default defineConfig({
  testDir: './e2e',
  // One worker, files in order: the verdict spec writes to the shared database.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  // No retries: a retried verdict spec would start from the state its first attempt wrote.
  retries: 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${DASHBOARD_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command:
        `uv run --package radar-api python ../scripts/seed_e2e_db.py ${DB_PATH}` +
        ` && uv run --package radar-api uvicorn radar_api.main:app --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/repositories`,
      env: {
        RADAR_DATABASE_URL: `sqlite:///${DB_PATH}`,
        RADAR_API_KEY: E2E_API_KEY,
        SENTRY_DSN: '',
      },
      // Always reseed: a reused server would keep the previous run's verdict changes.
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npx vite build && npx vite preview --port ${DASHBOARD_PORT} --strictPort`,
      url: `http://localhost:${DASHBOARD_PORT}`,
      env: { RADAR_API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
