const { test, expect } = require('@playwright/test');
const {
  clientCredentials,
  serviceCredentials,
  e2eServiceSlug,
  login,
  openJobCardOptionalDetails,
  selectFirstAvailableBookingSlot,
} = require('./helpers');

test.describe.serial('Flux principal AutoHub', () => {
  let scenario = {};

  test('clientul creeaza o programare noua din UI', async ({ page }) => {
    const suffix = String(Date.now()).slice(-6);
    scenario = {
      clientName: `Client E2E ${suffix}`,
      plate: `B${suffix}`,
      vin: `WVWZZZ1KZAW${suffix}`,
      phone: `0712${suffix}`,
      email: `client.e2e.${suffix}@example.com`,
      finalCost: '450',
    };

    await login(page, clientCredentials);
    await page.goto(`/bookings/programare/${e2eServiceSlug}/`);

    await page.locator('[name="car_brand"]').fill('Dacia');
    await page.locator('[name="car_model"]').fill('Logan');
    await page.locator('[name="car_year"]').fill('2022');
    await page.locator('[name="car_fuel"]').selectOption('benzina');
    await page.locator('[name="car_plate"]').fill(scenario.plate);
    await page.locator('[name="car_vin"]').fill(scenario.vin);

    await page.locator('[name="client_name"]').fill(scenario.clientName);
    await page.locator('[name="client_phone"]').fill(scenario.phone);
    await page.locator('[name="client_email"]').fill(scenario.email);
    await page.getByTestId('booking-problem-description').fill('Revizie completa E2E si verificare frane.');

    await selectFirstAvailableBookingSlot(page);

    await Promise.all([
      page.waitForURL(/\/bookings\/confirmare\/\d+\//),
      page.getByTestId('confirm-booking-button').click(),
    ]);

    await page.goto('/bookings/programarile-mele/');
    const bookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingCard).toBeVisible();
    await expect(bookingCard.getByTestId('client-booking-status')).toContainText(/așteptare|asteptare|pending/i);
  });

  test('service-ul gaseste bookingul si finalizeaza lucrarea', async ({ page }) => {
    await login(page, serviceCredentials);
    await page.goto('/services/dashboard/programari/');

    await page.getByTestId('service-bookings-search').fill(scenario.plate);
    const bookingRow = page.locator('[data-testid="service-booking-row"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingRow).toBeVisible();
    await bookingRow.click();

    await page.getByTestId('job-card-final-cost').fill(scenario.finalCost);
    await openJobCardOptionalDetails(page);
    await page.getByTestId('job-card-customer-notes').fill('Lucrare finalizata in scenariul E2E.');
    await page.getByTestId('job-card-save-button').click();

    await page.getByTestId('booking-status-select').selectOption('done');
    await page.getByTestId('booking-status-submit').click();
    await expect(page.getByTestId('service-booking-status-badge')).toContainText(/finaliz/i);
  });

  test('clientul vede statusul si costul final actualizat', async ({ page }) => {
    await login(page, clientCredentials);
    await page.goto('/bookings/programarile-mele/');

    const bookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingCard).toBeVisible();
    await expect(bookingCard.getByTestId('client-booking-status')).toContainText(/finaliz/i);
    await expect(bookingCard).toContainText(scenario.finalCost);
  });
});
