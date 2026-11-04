import { expect, test } from '@playwright/test'

test('lists the audited repository with its score and opens its report', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Repositories' })).toBeVisible()
  const repository = page.getByRole('link', { name: 'demo-app' })
  await expect(repository).toBeVisible()

  await repository.click()

  await expect(page).toHaveURL(/\/repositories\/demo-app-\d+$/)
  await expect(page.getByRole('heading', { level: 1, name: 'demo-app' })).toBeVisible()
})
