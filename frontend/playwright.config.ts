import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests', workers: 1, timeout: 45000,
  outputDir: '../.cache/browser-results',
  reporter: [['list'], ['html', { outputFolder: '../.cache/browser-report', open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5129', channel: 'chrome', trace: 'retain-on-failure',
    screenshot: 'only-on-failure', viewport: { width: 1440, height: 900 },
    launchOptions:{args:['--use-fake-device-for-media-stream']} },
  webServer: { command: '..\\.venv\\Scripts\\python.exe ..\\scripts\\browser_server.py',
    url: 'http://127.0.0.1:5129/api/ed/health', reuseExistingServer: false, timeout: 30000 },
})
