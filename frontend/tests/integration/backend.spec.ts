import { expect, test } from '@playwright/test'

const api = 'http://127.0.0.1:5196/api/v1'

test('shows a genuine backend 400 and retries without mock fallback', async ({ page }) => {
  let reject = true
  await page.route('**/api/v1/search/text', async route => {
    if (reject) {
      reject = false
      await route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), page: 0 }) })
    } else await route.continue()
  })
  await page.goto('/')
  await page.getByRole('searchbox').fill('glb')
  const rejected = page.waitForResponse(response => response.url().endsWith('/search/text') && response.status() === 400)
  await page.getByRole('searchbox').press('Enter')
  expect((await (await rejected).json()).error.code).toBe('INVALID_REQUEST')
  await expect(page.getByRole('alert')).toContainText('Yêu cầu tìm kiếm không hợp lệ')
  await expect(page.getByRole('list', { name: 'Kết quả asset' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Thử lại', exact: true }).click()
  await expect(page.locator('.asset-grid > li')).toHaveCount(6)
})

test('paginates the backend results and sends filters before pagination', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('searchbox').fill('glb')
  await page.getByRole('searchbox').press('Enter')
  await expect(page.locator('.asset-grid > li')).toHaveCount(6)
  await page.getByLabel('Số kết quả').selectOption('2')
  await page.getByRole('searchbox').press('Enter')
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 3 · 6 kết quả')
  await page.getByRole('button', { name: 'Trang sau' }).click()
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 3')
  await expect(page.getByRole('heading', { name: 'Bàn gỗ tròn', exact: true })).toBeVisible()
  await expect(page.locator('.rank').first()).toHaveText('Hạng 1')
  await page.getByRole('button', { name: 'Trang trước' }).click()
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 3')
  await page.getByText('Bộ lọc', { exact: true }).click()
  await page.getByLabel('Danh mục', { exact: true }).fill('Đồ gia dụng')
  await page.getByLabel('Định dạng', { exact: true }).fill('glb')
  const filtered = page.waitForResponse(response => response.url().endsWith('/search/text'))
  await page.getByRole('button', { name: 'Áp dụng bộ lọc' }).click()
  const response = await filtered
  expect(response.request().postDataJSON()).toMatchObject({ filters: { category: 'Đồ gia dụng', format: 'glb' }, page: 1, limit: 2 })
  await expect(page.locator('.asset-grid > li')).toHaveCount(2)
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 1 · 2 kết quả')
  await expect(page.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
  await page.getByLabel('License', { exact: true }).fill('CC0')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc' }).click()
  await expect(page.getByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('browses catalog list, filters, paginates, opens asset detail and returns with state preserved against FastAPI', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Bộ lọc', { exact: true }).click()
  await page.getByLabel('Danh mục', { exact: true }).fill('Nội thất')
  await page.getByRole('button', { name: 'Danh sách asset' }).click()
  await expect(page.getByRole('heading', { name: 'Danh sách asset' })).toBeVisible()
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 1 · 3 kết quả')
  await page.getByLabel('Số kết quả').selectOption('2')
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 2 · 3 kết quả')
  await page.getByRole('button', { name: 'Trang sau' }).click()
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 2 · 3 kết quả')
  await expect(page.getByRole('heading', { name: 'Bàn gỗ tròn' })).toBeVisible()
  await page.getByRole('button', { name: 'Xem chi tiết Bàn gỗ tròn' }).click()
  await expect(page.getByRole('region', { name: 'Chi tiết asset' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Quay lại danh sách' })).toBeFocused()
  await expect(page.getByRole('heading', { name: 'Bàn gỗ tròn' })).toBeVisible()
  await expect(page.getByText('mock-table-01')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.keyboard.press('Enter')
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 2 · 3 kết quả')
  await expect(page.getByRole('heading', { name: 'Bàn gỗ tròn' })).toBeVisible()
  await page.getByText('Bộ lọc', { exact: true }).click()
  await expect(page.getByLabel('Danh mục', { exact: true })).toHaveValue('Nội thất')
  await page.getByRole('button', { name: 'Đặt lại bộ lọc API' }).click()
  await expect(page.locator('.search-pagination')).toContainText('Trang 1 / 3 · 6 kết quả')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('checks list/detail, empty pages, validation, upload and Boolean feedback against FastAPI', async ({ request }) => {
  const listing = await request.get(`${api}/assets?page=2&limit=2&category=Nội%20thất`)
  expect(listing.status()).toBe(200)
  expect((await listing.json()).pagination).toEqual({ page: 2, limit: 2, total: 3, pages: 2, has_next: false })
  expect((await request.get(`${api}/assets/mock-chair-01`)).status()).toBe(200)
  expect((await request.get(`${api}/assets/missing`)).status()).toBe(404)
  for (const data of [
    { query: 'glb', filters: { unknown: 'x' } },
    { query: 'glb', filters: { face_count_min: 4, face_count_max: 1 } },
    { query: 'glb', page: true }, { query: '' },
  ]) expect((await request.post(`${api}/search/text`, { data })).status()).toBe(400)
  const empty = await request.post(`${api}/search/text`, { data: { query: 'glb', page: 99, limit: 2 } })
  expect(empty.status()).toBe(200)
  expect((await empty.json()).results).toEqual([])
  const nullCount = await request.post(`${api}/search/text`, { data: { query: 'glb', filters: { face_count_min: 0 } } })
  expect((await nullCount.json()).pagination.total).toBe(0)
  // Self-created 2x2 RGB PNG; no downloaded asset or external license.
  const image = { name: 'fixture.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGOU0zBiYGBgYmBgYGBgAAAFtgB8vDpoIwAAAABJRU5ErkJggg==', 'base64') }
  const upload = await request.post(`${api}/search/image`, { multipart: { image, filters: JSON.stringify({ category: 'Nội thất' }), page: '2', limit: '2' } })
  expect(upload.status()).toBe(200)
  const result = await upload.json()
  expect(result.query).toMatch(/^mock-image:[a-f0-9]{64}$/)
  expect(result.pagination).toEqual({ page: 2, limit: 2, total: 3, pages: 2, has_next: false })
  expect(result.results[0].rank).toBe(1)
  expect((await request.post(`${api}/search/image`, { multipart: { image: { ...image, buffer: Buffer.from('broken') } } })).status()).toBe(400)
  expect((await request.post(`${api}/search/image`, { multipart: { image, filters: 'broken' } })).status()).toBe(400)
  const feedback = { search_event_id: result.search_event_id, asset_id: result.results[0].asset.asset_id }
  for (const relevance of [true, false]) {
    const saved = await request.post(`${api}/feedback`, { data: { ...feedback, relevance } })
    expect(saved.status()).toBe(201)
    expect(await saved.json()).toMatchObject({ ...feedback, relevance, storage: 'memory', mock: true })
  }
  for (const relevance of [0, 1, 'true']) expect((await request.post(`${api}/feedback`, { data: { ...feedback, relevance } })).status()).toBe(400)
  expect((await request.post(`${api}/feedback`, { data: { ...feedback, asset_id: 'mock-lamp-01', relevance: true } })).status()).toBe(400)
  expect((await request.post(`${api}/feedback`, { data: { ...feedback, search_event_id: 'missing', relevance: false } })).status()).toBe(404)
})
