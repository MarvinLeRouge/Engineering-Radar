import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'demo-app' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'demo-app' })).toBeVisible()
})

test("shows the weighted risk of the latest run with the won't-fix note", async ({ page }) => {
  const riskBar = page.locator('.risk-bar')

  await expect(riskBar.getByTestId('risk-total')).toHaveText('33')
  await expect(riskBar.getByTestId('risk-legend-item')).toHaveText([
    "High 2 x16 = 32 (+1 won't fix, not counted)",
    'Low 1 x1 = 1',
  ])
})

test('counts findings by severity, leaving false positives out', async ({ page }) => {
  const summary = page.locator('.report-severity-summary')

  await expect(summary.getByTestId('severity-chip')).toHaveText(['HIGH (1 / 3)', 'LOW (1 / 1)'])
  await expect(summary.getByTestId('dismissed-count')).toHaveText(
    '1 finding dismissed as false positive, not counted',
  )
})

test('lists a dismissed false positive in its collapsed section', async ({ page }) => {
  const dismissed = page.getByTestId('dismissed-findings')

  await expect(dismissed.locator('summary')).toHaveText('Dismissed as false positive (1)')
  await expect(
    dismissed.getByText('Possible AWS key in config/example.env', { exact: true }),
  ).toBeHidden()

  await dismissed.locator('summary').click()

  await expect(
    dismissed.getByText('Possible AWS key in config/example.env', { exact: true }),
  ).toBeVisible()
})

test('shows the score and risk history across both audits', async ({ page }) => {
  await page.getByRole('button', { name: 'Trends' }).click()

  await expect(page.getByRole('heading', { name: 'Global score history' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Weighted risk history' })).toBeVisible()
  await expect(page.getByRole('img', { name: 'Weighted risk history' })).toBeVisible()
})
