# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> onetix dashboard smoke >> alerts list loads and opens alert review
- Location: e2e\smoke.spec.ts:20:7

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/app\/alerts/
Received string:  "http://localhost:4200/login"
Timeout: 5000ms

Call log:
  - Expect "toHaveURL" with timeout 5000ms
    14 × locator resolved to <html lang="en">…</html>
       - unexpected value "http://localhost:4200/login"

```

```yaml
- heading "onetix" [level=1]
- paragraph: Staff Console
- text: Email
- textbox "Email": admin@onevo.local
- text: Password
- textbox "Password": Admin123!
- button "Sign in"
- alert: Login failed
- paragraph: "Dev: admin@onevo.local / Admin123!"
- paragraph:
  - link "Back to home":
    - /url: /
```

# Test source

```ts
  1  | import { expect, test } from '@playwright/test';
  2  | 
  3  | const email = process.env.E2E_EMAIL || 'admin@onevo.local';
  4  | const password = process.env.E2E_PASSWORD || 'Admin123!';
  5  | 
  6  | async function login(page: import('@playwright/test').Page): Promise<void> {
  7  |   await page.goto('/login');
  8  |   await page.getByLabel('Email').fill(email);
  9  |   await page.getByLabel('Password').fill(password);
  10 |   await page.getByRole('button', { name: 'Sign in' }).click();
> 11 |   await expect(page).toHaveURL(/\/app\/alerts/);
     |                      ^ Error: expect(page).toHaveURL(expected) failed
  12 |   await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible();
  13 | }
  14 | 
  15 | test.describe('onetix dashboard smoke', () => {
  16 |   test('login lands on alerts', async ({ page }) => {
  17 |     await login(page);
  18 |   });
  19 | 
  20 |   test('alerts list loads and opens alert review', async ({ page }) => {
  21 |     await login(page);
  22 |     const reviewBtn = page.getByRole('button', { name: 'Review' }).first();
  23 |     const hasAlerts = await reviewBtn.isVisible().catch(() => false);
  24 |     test.skip(!hasAlerts, 'No alerts in seeded data');
  25 | 
  26 |     await reviewBtn.click();
  27 |     await expect(page).toHaveURL(/\/app\/alerts\/.+/);
  28 |     await expect(page.getByRole('heading', { name: 'Review' })).toBeVisible();
  29 |     await page.getByRole('button', { name: 'Submit review' }).click();
  30 |     await expect(page.getByText('Review saved.')).toBeVisible({ timeout: 15_000 });
  31 |   });
  32 | 
  33 |   test('store filter updates query param', async ({ page }) => {
  34 |     await login(page);
  35 |     const storeSelect = page.getByLabel('Store filter');
  36 |     const optionCount = await storeSelect.locator('option').count();
  37 |     test.skip(optionCount < 2, 'Need at least one store besides All stores');
  38 | 
  39 |     const firstStoreValue = await storeSelect.locator('option').nth(1).getAttribute('value');
  40 |     const firstStoreLabel = await storeSelect.locator('option').nth(1).textContent();
  41 |     test.skip(!firstStoreValue, 'No store option value');
  42 | 
  43 |     await storeSelect.selectOption(firstStoreValue!);
  44 |     await expect(page).toHaveURL(new RegExp(`storeId=${firstStoreValue}`));
  45 |     await expect(storeSelect).toHaveValue(firstStoreValue!);
  46 |     if (firstStoreLabel) {
  47 |       await expect(storeSelect.locator('option:checked')).toHaveText(firstStoreLabel.trim());
  48 |     }
  49 |   });
  50 | });
  51 | 
  52 | test.describe('mobile shell', () => {
  53 |   test.use({ viewport: { width: 390, height: 844 } });
  54 | 
  55 |   test('drawer opens and closes', async ({ page }) => {
  56 |     await login(page);
  57 |     const menuBtn = page.getByRole('button', { name: 'Toggle menu' });
  58 |     await menuBtn.click();
  59 |     await expect(page.locator('.sidebar.open')).toBeVisible();
  60 |     await expect(menuBtn).toHaveAttribute('aria-expanded', 'true');
  61 | 
  62 |     await page.locator('.sidebar-backdrop.open').click();
  63 |     await expect(page.locator('.sidebar.open')).toHaveCount(0);
  64 |     await expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
  65 |   });
  66 | });
  67 | 
```