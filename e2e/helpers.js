const { expect } = require('@playwright/test');

const clientCredentials = {
  username: process.env.E2E_CLIENT_USERNAME || 'client_e2e',
  password: process.env.E2E_CLIENT_PASSWORD || 'client12345',
};

const serviceCredentials = {
  username: process.env.E2E_SERVICE_USERNAME || 'service_e2e',
  password: process.env.E2E_SERVICE_PASSWORD || 'service12345',
};

const e2eServiceSlug = process.env.E2E_SERVICE_SLUG || 'autohub-e2e-service';

async function login(page, credentials) {
  await page.goto('/accounts/logout/');
  await page.goto('/accounts/login/');
  await page.getByTestId('login-username').fill(credentials.username);
  await page.getByTestId('login-password').fill(credentials.password);
  await Promise.all([
    page.waitForLoadState('networkidle'),
    page.getByTestId('login-submit').click(),
  ]);
}

async function openJobCardOptionalDetails(page) {
  const optionalDetails = page.getByTestId('job-card-optional-details');
  if ((await optionalDetails.getAttribute('open')) === null) {
    await page.getByTestId('job-card-optional-details-toggle').click();
  }
  await expect(page.getByTestId('job-card-customer-notes')).toBeVisible();
}

async function selectFirstAvailableBookingSlot(page) {
  const dateCards = page.getByTestId('booking-date-card');
  const totalDates = await dateCards.count();

  for (let index = 0; index < totalDates; index += 1) {
    await dateCards.nth(index).click();
    await page.locator('#card-garaje').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('#g-loading').waitFor({ state: 'hidden', timeout: 15000 });

    const slotButtons = page.getByTestId('booking-slot-button');
    if (await slotButtons.count()) {
      await expect(slotButtons.first()).toBeVisible();
      await slotButtons.first().click();
      return;
    }
  }

  throw new Error('No available booking slot was rendered for the displayed booking dates.');
}

module.exports = {
  clientCredentials,
  serviceCredentials,
  e2eServiceSlug,
  login,
  openJobCardOptionalDetails,
  selectFirstAvailableBookingSlot,
};
