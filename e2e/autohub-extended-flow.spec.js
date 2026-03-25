const { test, expect } = require('@playwright/test');
const {
  clientCredentials,
  serviceCredentials,
  e2eServiceSlug,
  login,
  openJobCardOptionalDetails,
  selectFirstAvailableBookingSlot,
} = require('./helpers');

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

async function createBookingFromClient(page, scenario, { wantsOffer = false } = {}) {
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

  if (wantsOffer) {
    await page.getByTestId('booking-offer-toggle').click();
  }

  await selectFirstAvailableBookingSlot(page);

  await Promise.all([
    page.waitForURL(/\/bookings\/confirmare\/\d+\//),
    page.getByTestId('confirm-booking-button').click(),
  ]);
}

async function openBookingDetailForPlate(page, plate) {
  await login(page, serviceCredentials);
  await page.goto('/services/dashboard/programari/');
  await page.getByTestId('service-bookings-search').fill(plate);
  const row = page.locator('[data-testid="service-booking-row"]').filter({ hasText: plate }).first();
  await expect(row).toBeVisible();
  await row.click();
}

test.describe.serial('Flux oferta acceptata si factura', () => {
  const suffix = String(Date.now()).slice(-6);
  const scenario = {
    clientName: `Client Oferta ${suffix}`,
    plate: `BOF${suffix}`,
    vin: `WVWZZZ1KZAW${suffix}`,
    phone: `0722${suffix}`,
    email: `oferta.acceptata.${suffix}@example.com`,
    problem: 'Masina trage dreapta si solicit oferta inainte de confirmare.',
  };

  test('clientul cere oferta inainte de confirmare', async ({ page }) => {
    await createBookingFromClient(page, scenario, { wantsOffer: true });
    await page.goto('/bookings/programarile-mele/');
    const bookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingCard).toBeVisible();
    await expect(bookingCard.getByTestId('client-booking-status')).toContainText(/așteptare|asteptare|pending/i);
  });

  test('service-ul trimite oferta pentru bookingul clientului', async ({ page }) => {
    await openBookingDetailForPlate(page, scenario.plate);
    await page.getByTestId('service-quote-price-input').fill('320');
    await page.getByTestId('service-quote-duration-select').selectOption('90');
    await page.getByTestId('service-send-quote-button').click();

    await page.goto('/services/dashboard/programari/');
    await page.getByTestId('service-bookings-search').fill(scenario.plate);
    const row = page.locator('[data-testid="service-booking-row"]').filter({ hasText: scenario.plate }).first();
    await expect(row).toContainText(/oferta|trimisa/i);
  });

  test('clientul accepta oferta si vede bookingul confirmat', async ({ page }) => {
    await login(page, clientCredentials);
    await page.goto('/bookings/programarile-mele/');

    const bookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingCard).toBeVisible();
    await bookingCard.getByTestId('client-accept-quote-button').click();

    await expect(bookingCard.getByTestId('client-booking-status')).toContainText(/confirm/i);
    await expect(bookingCard).toContainText('320');
  });

  test('service-ul finalizeaza bookingul si emite factura din UI', async ({ page }) => {
    const invoiceSuffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`.slice(-6);
    const invoiceScenario = {
      clientName: `Client Factura ${invoiceSuffix}`,
      plate: `BIF${invoiceSuffix}`,
      vin: `WVWZZZ1KZAW${invoiceSuffix}`,
      phone: `0744${invoiceSuffix}`,
      email: `factura.e2e.${invoiceSuffix}@example.com`,
      problem: 'Scenariu complet E2E pentru emiterea facturii din booking confirmat.',
    };

    await createBookingFromClient(page, invoiceScenario, { wantsOffer: true });

    await openBookingDetailForPlate(page, invoiceScenario.plate);
    await page.getByTestId('service-quote-price-input').fill('320');
    await page.getByTestId('service-quote-duration-select').selectOption('90');
    await page.getByTestId('service-send-quote-button').click();

    await login(page, clientCredentials);
    await page.goto('/bookings/programarile-mele/');
    const invoiceBookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: invoiceScenario.plate }).first();
    await expect(invoiceBookingCard).toBeVisible();
    await invoiceBookingCard.getByTestId('client-accept-quote-button').click();
    await expect(invoiceBookingCard.getByTestId('client-booking-status')).toContainText(/confirm/i);

    await openBookingDetailForPlate(page, invoiceScenario.plate);

    await page.getByTestId('job-card-final-cost').fill('320');
    await openJobCardOptionalDetails(page);
    await page.getByTestId('job-card-customer-notes').fill('Oferta acceptata si lucrarea a fost finalizata.');
    await page.getByTestId('job-card-save-button').click();

    await page.getByTestId('booking-status-select').selectOption('done');
    await page.getByTestId('booking-status-submit').click();
    await expect(page.getByTestId('service-booking-status-badge')).toContainText(/finaliz/i);

    await Promise.all([
      page.waitForURL(/\/facturi\/creare\/\?booking=\d+/),
      page.getByTestId('open-invoice-create').click(),
    ]);
    await expect(page.getByTestId('invoice-client-name')).toHaveValue(invoiceScenario.clientName);
    await page.locator('[name="issue_date"]').fill(todayIso());

    await page.locator('[data-testid="invoice-line-description"]').first().fill('Geometrie roti si diagnoza directie');
    await page.locator('[data-testid="invoice-line-quantity"]').first().fill('1');
    await page.locator('[data-testid="invoice-line-unit-price"]').first().fill('320');
    await Promise.all([
      page.waitForURL(/\/facturi\/\d+\/$/),
      page.getByTestId('invoice-finalize-button').click(),
    ]);

    await expect(page).toHaveURL(/\/facturi\/\d+\/$/);
    await expect(page.getByTestId('invoice-detail-title')).toContainText(/factur/i);
    await expect(page.getByTestId('invoice-total-value')).toContainText('320');
  });
});

test.describe.serial('Flux oferta refuzata', () => {
  const suffix = String(Date.now() + 101).slice(-6);
  const scenario = {
    clientName: `Client Refuz ${suffix}`,
    plate: `BRJ${suffix}`,
    vin: `WVWZZZ1KZAW${suffix}`,
    phone: `0733${suffix}`,
    email: `oferta.refuzata.${suffix}@example.com`,
    problem: 'Clientul cere oferta, dar o va refuza in scenariul E2E.',
  };

  test('clientul creeaza booking cu oferta obligatorie', async ({ page }) => {
    await createBookingFromClient(page, scenario, { wantsOffer: true });
    await page.goto('/bookings/programarile-mele/');
    const bookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingCard).toBeVisible();
  });

  test('service-ul trimite oferta pentru bookingul care va fi refuzat', async ({ page }) => {
    await openBookingDetailForPlate(page, scenario.plate);
    await page.getByTestId('service-quote-price-input').fill('210');
    await page.getByTestId('service-quote-duration-select').selectOption('60');
    await page.getByTestId('service-send-quote-button').click();
    await page.goto('/services/dashboard/programari/');
    await page.getByTestId('service-bookings-search').fill(scenario.plate);
    await expect(page.locator('[data-testid="service-booking-row"]').filter({ hasText: scenario.plate }).first()).toContainText(/ofertă|oferta|trimisă|trimisa/i);
  });

  test('clientul refuza oferta si bookingul devine anulat', async ({ page }) => {
    await login(page, clientCredentials);
    await page.goto('/bookings/programarile-mele/');
    const bookingCard = page.locator('[data-testid="client-booking-card"]').filter({ hasText: scenario.plate }).first();
    await expect(bookingCard).toBeVisible();
    await bookingCard.getByTestId('client-reject-quote-button').click();
    await expect(bookingCard.getByTestId('client-booking-status')).toContainText(/anulat|cancel/i);
  });
});

test('service-ul poate inregistra miscari reale de stoc din inventar', async ({ page }) => {
  await login(page, serviceCredentials);
  await page.goto('/services/dashboard/piese/');

  await page.getByTestId('inventory-search-input').fill('Filtru ulei E2E');
  await page.getByRole('button', { name: 'Aplica' }).click();

  const row = page.locator('[data-testid="inventory-part-row"][data-part-name=\"filtru ulei e2e\"]').first();
  await expect(row).toBeVisible();
  await expect(row).toContainText('5 buc');

  await row.getByTestId('inventory-movement-type').selectOption('in');
  await row.getByTestId('inventory-movement-quantity').fill('3');
  await Promise.all([
    page.waitForURL(/\/services\/dashboard\/piese\/\?.*q=Filtru\+ulei\+E2E/i),
    row.getByTestId('inventory-log-movement-button').click(),
  ]);

  const updatedRow = page.locator('[data-testid="inventory-part-row"][data-part-name=\"filtru ulei e2e\"]').first();
  await expect(updatedRow).toContainText('8 buc');
  await expect(page.getByTestId('inventory-movement-item').first()).toContainText('Filtru ulei E2E');
});
