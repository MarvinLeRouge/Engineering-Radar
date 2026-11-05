import { expect, test } from '@playwright/test'
import { E2E_API_KEY } from '../playwright.config'

// Runs last (files run in order on one worker): it writes a verdict to the database.
test('marking a finding as false positive moves it out of the counts', async ({ page }) => {
  await page.goto('/settings')
  await page.getByLabel('API key').fill(E2E_API_KEY)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()

  await page.goto('/')
  await page.getByRole('link', { name: 'demo-app' }).click()
  const secrets = page.locator('.criterion', {
    has: page.getByRole('heading', { name: 'Secrets in tracked history' }),
  })
  await secrets.getByTestId('severity-chip').filter({ hasText: 'LOW' }).click()
  const card = secrets.locator('.finding-card', { hasText: 'Generic token in docs/setup.md' })
  await card.getByTestId('verdict-select').selectOption('FALSE_POSITIVE')

  await expect(secrets.getByTestId('dismissed-findings').locator('summary')).toHaveText(
    'Dismissed as false positive (2)',
  )
  await expect(page.locator('.report-severity-summary').getByTestId('severity-chip')).toHaveText([
    'HIGH (1 / 3)',
  ])
  await expect(page.locator('.risk-bar').getByTestId('risk-total')).toHaveText('32')

  const dismissed = secrets.getByTestId('dismissed-findings')
  await dismissed.locator('summary').click()
  const dismissedCard = dismissed.locator('.finding-card', {
    hasText: 'Generic token in docs/setup.md',
  })
  const note = dismissedCard.getByTestId('verdict-note')
  await note.fill('Framework convention, used at runtime')
  await note.press('Enter')
  await expect(dismissedCard.getByTestId('verdict-note-saved')).toBeVisible()

  await page.reload()
  await secrets.getByTestId('dismissed-findings').locator('summary').click()
  await expect(
    secrets
      .getByTestId('dismissed-findings')
      .locator('.finding-card', { hasText: 'Generic token in docs/setup.md' })
      .getByTestId('verdict-note'),
  ).toHaveValue('Framework convention, used at runtime')
})
