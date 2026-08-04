import { test, expect } from '@playwright/test';

// Temporary end-to-end verification of the training-dataset feature.
// Flow: login → open a pending alert → confirm with pattern selection →
// Training page shows the new sample → open detail → edit labels → exclude/include.

const BASE = 'http://localhost:4200';
const SHOT = (n: string) => `test-results/verify-${n}.png`;

test.setTimeout(180_000);

// Desktop-only: the flow drives the desktop table layout (mobile renders cards),
// and running it twice (chromium + mobile) would double-review the same alert.
test.skip(({ isMobile }) => !!isMobile, 'Desktop-only verification flow');

test('review with patterns creates a visible training sample', async ({ page }) => {
  // ---- Login as admin ----
  await page.goto(`${BASE}/login`);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SHOT('00-login') });
  await page.locator('input[type="email"], input[name="email"], input#email').first().fill('admin@onevo.local');
  await page.locator('input[type="password"]').first().fill('Admin123!');
  await page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login"), button:has-text("Log in")').first().click();
  await page.waitForURL(/\/app\//, { timeout: 20_000 });
  await page.screenshot({ path: SHOT('01-after-login') });

  // ---- Open Alerts and pick an alert ----
  await page.goto(`${BASE}/app/alerts`);
  await page.waitForLoadState('networkidle');

  // Default filter is "Needs review"; if the queue is empty (e.g. every alert
  // was already reviewed by a previous run), fall back to "All statuses" —
  // re-reviewing an alert upserts the same training sample, so the flow still verifies.
  const firstRow = page.locator('table tbody tr').first();
  const emptyState = page.getByText('No alerts — all clear');
  await expect(firstRow.or(emptyState)).toBeVisible({ timeout: 20_000 });
  if (await emptyState.isVisible()) {
    await page.getByLabel('Status filter').selectOption('');
    await page.waitForLoadState('networkidle');
  }
  await page.screenshot({ path: SHOT('02-alerts-list') });

  // Click the first row that opens a review pane. If there are truly no alerts
  // in the system at all, fail fast with a clear message instead of timing out.
  if (await emptyState.isVisible()) {
    throw new Error('No alerts exist in the system — seed at least one alert before running this test.');
  }
  await expect(firstRow).toBeVisible({ timeout: 20_000 });
  await firstRow.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: SHOT('03-review-pane'), fullPage: true });

  // ---- Pattern chips should be visible with AI pre-selection ----
  const fieldset = page.locator('fieldset.patterns');
  await expect(fieldset).toBeVisible({ timeout: 15_000 });
  const chips = fieldset.locator('label.chip');
  const chipCount = await chips.count();
  console.log('PATTERN_CHIPS:', chipCount);
  const preSelected = await fieldset.locator('label.chip.on').count();
  console.log('PRESELECTED:', preSelected);
  await fieldset.screenshot({ path: SHOT('04-pattern-chips') });

  // Toggle: untick one pre-selected, tick one unselected (simulate correction).
  if (preSelected > 0) {
    await fieldset.locator('label.chip.on').first().click();
  }
  const off = fieldset.locator('label.chip:not(.on)');
  if (await off.count() > 0) {
    await off.first().click();
  }
  await page.screenshot({ path: SHOT('05-chips-toggled'), fullPage: true });

  // Record which patterns are now selected.
  const selectedNames = await fieldset.locator('label.chip.on span').allInnerTexts();
  console.log('SELECTED_PATTERNS:', JSON.stringify(selectedNames));

  // ---- Confirm the incident ----
  await page.locator('button:has-text("Confirm")').first().click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: SHOT('06-after-confirm'), fullPage: true });

  // ---- Training page ----
  await page.goto(`${BASE}/app/training`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: SHOT('07-training-page'), fullPage: true });

  // Stats tiles present with at least one sample.
  const totalTile = page.locator('.stat-tile').first();
  await expect(totalTile).toBeVisible({ timeout: 15_000 });
  const totalText = await totalTile.locator('.sv').innerText();
  console.log('TOTAL_SAMPLES:', totalText);
  expect(Number(totalText)).toBeGreaterThan(0);

  // Table has rows; open first sample detail.
  const sampleRow = page.locator('table tbody tr').first();
  await expect(sampleRow).toBeVisible();
  await sampleRow.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: SHOT('08-sample-detail'), fullPage: true });

  const detailPanel = page.locator('.detail-panel');
  await expect(detailPanel).toBeVisible();
  const labelRows = await detailPanel.locator('.label-row').count();
  console.log('DETAIL_LABEL_ROWS:', labelRows);

  // ---- Edit labels from Training page ----
  await detailPanel.locator('button:has-text("Edit labels")').click();
  const editGrid = detailPanel.locator('.chip-grid');
  await expect(editGrid).toBeVisible();
  // Toggle first chip and save.
  await editGrid.locator('label.chip').first().click();
  await detailPanel.locator('button:has-text("Save labels")').click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SHOT('09-after-label-edit'), fullPage: true });

  // ---- Toggle include/exclude both ways (state-agnostic: a previous run may
  // have left the sample excluded, so start from whichever button is showing) ----
  const excludeBtn = detailPanel.locator('button:has-text("Exclude from training")');
  const includeBtn = detailPanel.locator('button:has-text("Include in training")');
  await expect(excludeBtn.or(includeBtn)).toBeVisible({ timeout: 10_000 });

  if (await includeBtn.isVisible()) {
    // Currently excluded → include first, then exclude/include below.
    await includeBtn.click();
    await expect(excludeBtn).toBeVisible({ timeout: 10_000 });
  }
  await excludeBtn.click();
  await expect(includeBtn).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: SHOT('10-excluded'), fullPage: true });
  await includeBtn.click();
  await expect(excludeBtn).toBeVisible({ timeout: 10_000 });
  console.log('INCLUDE_TOGGLE: ok');
});
