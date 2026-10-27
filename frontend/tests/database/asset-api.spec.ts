import { expect, test } from '@playwright/test'

test('PostgreSQL list → detail → back preserves filters, page and limit', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Bộ lọc', { exact: true }).click()
  await page.getByLabel('Danh mục', { exact: true }).fill('issue49-fixture')
  const listing = page.waitForResponse(r => r.url().includes('/api/v1/assets?') && r.status() === 200)
  await page.getByRole('button', { name: 'Danh sách asset' }).click()
  expect((await (await listing).json()).mock).toBe(false)
  await expect(page.locator('.search-pagination')).toContainText('3 kết quả')
  await page.getByLabel('Số kết quả').selectOption('2')
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 2')
  await page.getByRole('button', { name: 'Trang sau' }).click()
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 2')
  const detail = page.waitForResponse(r => r.url().endsWith('/assets/verify-3'))
  await page.getByRole('button', { name: 'Xem chi tiết API integration asset 3' }).click()
  expect((await (await detail).json()).mock).toBe(false)
  await expect(page.getByText('verify-3', { exact: true })).toBeVisible()
  await expect(page.getByText('Chưa có ảnh xem trước', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Quay lại danh sách', exact: true }).click()
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 2')
  await expect(page.getByLabel('Số kết quả')).toHaveValue('2')
  await page.getByText('Bộ lọc', { exact: true }).click()
  await expect(page.getByLabel('Danh mục', { exact: true })).toHaveValue('issue49-fixture')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('missing database asset shows a genuine backend 404', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Danh sách asset' }).click()
  await expect(page.getByRole('button', { name: 'Xem chi tiết API integration asset 1' })).toBeVisible()
  // Chuyển request tới ID thiếu; không giả lập response hoặc fallback fixture.
  await page.route('**/api/v1/assets/verify-1', route =>
    route.continue({ url: new URL('/api/v1/assets/missing-issue49', route.request().url()).href }))
  const missing = page.waitForResponse(r => r.status() === 404 && r.url().includes('/assets/'))
  await page.getByRole('button', { name: 'Xem chi tiết API integration asset 1' }).click()
  expect((await (await missing).json()).error.code).toBe('ASSET_NOT_FOUND')
  await expect(page.getByRole('heading', { name: 'Không tìm thấy asset', exact: true })).toBeVisible()
})

test('invalid list request shows a genuine backend 400 without fixture fallback', async ({ page }) => {
  await page.route('**/api/v1/assets?**', route => {
    const url = new URL(route.request().url())
    url.searchParams.set('limit', '0')
    return route.continue({ url: url.href })
  })
  await page.goto('/')
  const rejected = page.waitForResponse(r => r.status() === 400 && r.url().includes('/assets?'))
  await page.getByRole('button', { name: 'Danh sách asset' }).click()
  expect((await (await rejected).json()).error.code).toBe('INVALID_REQUEST')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('.asset-grid > li')).toHaveCount(0)
})
