import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  // shots.spec.ts is a dev helper for README screenshots: `SHOTS_DIR=... npx playwright test shots`
  testIgnore: process.env.SHOTS_DIR ? [] : ["**/shots.spec.ts"],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 1,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: `python -m http.server ${PORT} --bind 127.0.0.1 --directory out`, port: PORT, reuseExistingServer: true },
});
