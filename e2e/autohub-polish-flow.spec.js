const { test, expect } = require('@playwright/test');
const {
  clientCredentials,
  serviceCredentials,
  e2eServiceSlug,
  login,
  openJobCardOptionalDetails,
  selectFirstAvailableBookingSlot,
} = require('./helpers');

const e2eServiceName = 'AutoHub E2E Service';

function futureDateTime(offsetDays, hour, minute = 0) {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  value.setHours(hour, minute, 0, 0);
  return value.toISOString().slice(0, 16);
}

async function createClientBooking(page, scenario) {
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
  await page.getByTestId('booking-problem-description').fill(scenario.problem);

  await selectFirstAvailableBookingSlot(page);

  await Promise.all([
    page.waitForURL(/\/bookings\/confirmare\/\d+\//),
    page.getByTestId('confirm-booking-button').click(),
  ]);
}

async function finalizeBookingForPlate(page, plate, finalCost) {
  await login(page, serviceCredentials);
  await page.goto('/services/dashboard/programari/');
  await page.getByTestId('service-bookings-search').fill(plate);

  const row = page.locator('[data-testid="service-booking-row"]').filter({ hasText: plate }).first();
  await expect(row).toBeVisible();
  await row.click();

  await page.getByTestId('job-card-final-cost').fill(finalCost);
  await openJobCardOptionalDetails(page);
  await page.getByTestId('job-card-customer-notes').fill('Finalizat in scenariul E2E de review.');
  await page.getByTestId('job-card-save-button').click();
  await page.getByTestId('booking-status-select').selectOption('done');
  await page.getByTestId('booking-status-submit').click();
  await expect(page.getByTestId('service-booking-status-badge')).toContainText(/finaliz/i);
}

test.describe.serial('Fluxuri E2E de polish', () => {
  test('clientul poate adauga si elimina service-ul din favorite', async ({ page }) => {
    await login(page, clientCredentials);
    await page.goto(`/services/${e2eServiceSlug}/`);

    const favoriteButton = page.getByTestId('service-detail-favorite-button');
    await expect(favoriteButton).toBeVisible();

    if ((await favoriteButton.textContent()).includes('Scoate')) {
      await Promise.all([
        page.waitForLoadState('networkidle'),
        favoriteButton.click(),
      ]);
      await expect(page.getByTestId('service-detail-favorite-button')).toContainText(/Adaugă|Adauga/i);
    }

    await Promise.all([
      page.waitForLoadState('networkidle'),
      page.getByTestId('service-detail-favorite-button').click(),
    ]);
    await expect(page.getByTestId('service-detail-favorite-button')).toContainText(/Scoate/i);

    await page.goto('/accounts/profil/');
    await expect(page.getByTestId('profile-favorite-card').filter({ hasText: e2eServiceName })).toBeVisible();

    await page.goto(`/services/${e2eServiceSlug}/`);
    await Promise.all([
      page.waitForLoadState('networkidle'),
      page.getByTestId('service-detail-favorite-button').click(),
    ]);
    await expect(page.getByTestId('service-detail-favorite-button')).toContainText(/Adaugă|Adauga/i);
  });

  test('clientul poate lasa o recenzie dupa o lucrare finalizata', async ({ page }) => {
    const suffix = String(Date.now()).slice(-6);
    const scenario = {
      clientName: `Client Review ${suffix}`,
      plate: `BRV${suffix}`,
      vin: `WVWZZZ1KZAW${suffix}`,
      phone: `0728${suffix}`,
      email: `review.e2e.${suffix}@example.com`,
      problem: 'Scenariu E2E pentru recenzie dupa lucrare finalizata.',
      finalCost: '390',
      reviewTitle: `Recenzie E2E ${suffix}`,
      reviewBody: 'Tot fluxul a mers bine, iar masina a fost predata la timp.',
    };

    await createClientBooking(page, scenario);
    await finalizeBookingForPlate(page, scenario.plate, scenario.finalCost);

    await login(page, clientCredentials);
    await page.goto(`/services/${e2eServiceSlug}/`);
    await expect(page.getByTestId('service-review-form')).toBeVisible();

    await page.locator('[name="rating"]').selectOption('5');
    await page.locator('[name="title"]').fill(scenario.reviewTitle);
    await page.locator('[name="body"]').fill(scenario.reviewBody);
    await Promise.all([
      page.waitForLoadState('networkidle'),
      page.getByTestId('service-review-submit').click(),
    ]);

    await expect(page.getByTestId('service-review-item').filter({ hasText: scenario.reviewTitle }).first()).toBeVisible();
  });

  test('service-ul poate bloca un interval si vede filtrele neactivate implicit', async ({ page }) => {
    const suffix = String(Date.now()).slice(-6);
    const blockTitle = `Blocaj E2E ${suffix}`;

    await login(page, serviceCredentials);
    await page.goto('/services/dashboard/calendar/');

    await expect(page.locator('[data-testid="calendar-status-pill"].active')).toHaveCount(0);
    const confirmedPill = page.locator('[data-testid="calendar-status-pill"][data-status="confirmed"]').first();
    await confirmedPill.click();
    await expect(confirmedPill).toHaveClass(/active/);

    await page.locator('[name="garage"]').selectOption({ index: 1 });
    await page.locator('[name="block_type"]').selectOption('break');
    await page.locator('[name="title"]').fill(blockTitle);
    await page.locator('[name="starts_at"]').fill(futureDateTime(2, 12, 0));
    await page.locator('[name="ends_at"]').fill(futureDateTime(2, 13, 0));
    await Promise.all([
      page.waitForLoadState('networkidle'),
      page.getByTestId('calendar-block-submit').click(),
    ]);

    await expect(page.getByTestId('calendar-block-item').filter({ hasText: blockTitle }).first()).toBeVisible();
  });
});
