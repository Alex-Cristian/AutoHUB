const { defineConfig, devices } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const port = process.env.E2E_PORT || '8010';
const baseURL = process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`;
const localPython = process.platform === 'win32'
  ? path.join(__dirname, '.venv', 'Scripts', 'python.exe')
  : path.join(__dirname, '.venv', 'bin', 'python');
const pythonCmd = fs.existsSync(localPython) ? `"${localPython}"` : 'python';

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 90 * 1000,
  expect: {
    timeout: 15 * 1000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: `${pythonCmd} manage.py prepare_e2e_data && ${pythonCmd} manage.py runserver 127.0.0.1:${port}`,
    env: {
      ...process.env,
      DEBUG: 'True',
      SITE_BASE_URL: baseURL,
      TWILIO_SMS_ENABLED: 'False',
      EMAIL_BACKEND: 'django.core.mail.backends.locmem.EmailBackend',
      USE_CLOUDINARY: 'False',
    },
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120 * 1000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
