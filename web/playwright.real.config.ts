import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-real",
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4174",
    channel: "chrome",
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  webServer: [
    {
      command:
        '"..\\.venv\\Scripts\\python.exe" -m cookkg.cli serve --graph "..\\data\\processed\\v2\\backend-graph.json" --host 127.0.0.1 --port 8010',
      cwd: ".",
      env: {
        COOKKG_CORS_ORIGINS: "http://127.0.0.1:4174",
        PYTHONPATH: "../src",
      },
      url: "http://127.0.0.1:8010/api/health",
      reuseExistingServer: true,
    },
    {
      command: "pnpm dev --host 127.0.0.1 --port 4174",
      env: {
        VITE_API_BASE_URL: "http://127.0.0.1:8010",
        VITE_USE_MOCKS: "false",
      },
      url: "http://127.0.0.1:4174",
      reuseExistingServer: true,
    },
  ],
});
