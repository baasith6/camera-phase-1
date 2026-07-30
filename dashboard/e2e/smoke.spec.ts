import { expect, test } from '@playwright/test';

const email = process.env.E2E_EMAIL || 'admin@onevo.local';
const password = process.env.E2E_PASSWORD || 'Admin123!';

async function login(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/app\/alerts/);
  await expect(page.getByRole('heading', { name: 'Review' })).toBeVisible();
}

test.describe('onetix dashboard smoke', () => {
  test('login lands on alerts', async ({ page }) => {
    await login(page);
  });

  test('alerts list loads and opens alert review', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    const reviewBtn = page.getByRole('button', { name: 'Review' }).first();
    const hasAlerts = await reviewBtn.isVisible().catch(() => false);
    test.skip(!hasAlerts, 'No alerts in seeded data');

    await reviewBtn.click();
    await expect(page).toHaveURL(/\/app\/alerts\/.+/);
    await expect(page.getByRole('heading', { name: 'Your review', level: 4 })).toBeVisible();
    await page.getByRole('button', { name: 'Confirm incident' }).click();
    await expect(page.getByText('Review saved.')).toBeVisible({ timeout: 15_000 });
  });

  test('store filter updates query param', async ({ page }) => {
    await login(page);
    const storeSelect = page.getByLabel('Store filter');
    const optionCount = await storeSelect.locator('option').count();
    test.skip(optionCount < 2, 'Need at least one store besides All stores');

    const firstStoreValue = await storeSelect.locator('option').nth(1).getAttribute('value');
    const firstStoreLabel = await storeSelect.locator('option').nth(1).textContent();
    test.skip(!firstStoreValue, 'No store option value');

    await storeSelect.selectOption(firstStoreValue!);
    await expect(page).toHaveURL(new RegExp(`storeId=${firstStoreValue}`));
    await expect(storeSelect).toHaveValue(firstStoreValue!);
    if (firstStoreLabel) {
      await expect(storeSelect.locator('option:checked')).toHaveText(firstStoreLabel.trim());
    }
  });
});

test.describe('mobile shell', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('drawer opens and closes', async ({ page }) => {
    await login(page);
    const menuBtn = page.getByRole('button', { name: 'Toggle menu' });
    await menuBtn.click();
    await expect(page.locator('.sidebar.open')).toBeVisible();
    await expect(menuBtn).toHaveAttribute('aria-expanded', 'true');

    await page.locator('.sidebar-backdrop.open').click();
    await expect(page.locator('.sidebar.open')).toHaveCount(0);
    await expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
  });

  test('clips page shows mobile cards', async ({ page }) => {
    await login(page);
    await page.goto('/app/clips');
    await expect(page.getByRole('heading', { name: 'Clips' })).toBeVisible();

    const emptyState = page.getByText('No clips uploaded yet');
    const mobileCards = page.locator('.alert-card-mobile');
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const cardCount = await mobileCards.count();

    expect(hasEmpty || cardCount > 0).toBeTruthy();
    if (cardCount > 0) {
      await expect(mobileCards.first()).toBeVisible();
      await expect(page.locator('.data-table-desktop')).toBeHidden();
    }
  });
});
