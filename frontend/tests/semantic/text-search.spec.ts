import { expect, test as base, type Page } from '@playwright/test'
import type { LiveTextSearchResponse } from './types'

const test = base.extend<{ capture: void }>({
  capture: [async ({ page }, use, testInfo) => {
    const observations: unknown[] = []
    const pending: Promise<void>[] = []
    page.on('response', (response) => {
      if (response.url() === `${process.env.TEXT_SEARCH_API_URL}/api/v1/search/text`
        && response.request().method() === 'POST') {
        pending.push(response.json().then((body: unknown) => {
          observations.push({ payload: response.request().postDataJSON(), status: response.status(), body })
        }))
      }
    })
    await use()
    await Promise.all(pending)
    await testInfo.attach('real-text-search-http', {
      body: JSON.stringify(observations), contentType: 'application/json',
    })
  }, { auto: true }],
})

// Chỉ lắng nghe HTTP thật. Không route.fulfill/intercept response API.
async function search(page: Page, action: () => Promise<unknown>, status = 200) {
  const pending = page.waitForResponse((response) =>
    response.url() === `${process.env.TEXT_SEARCH_API_URL}/api/v1/search/text`
    && response.request().method() === 'POST')
  await action()
  const response = await pending
  expect(response.status()).toBe(status)
  return response
}

async function assertResults(page: Page, body: LiveTextSearchResponse) {
  expect(body.mock).toBe(false)
  expect(body.query_id).toBe(body.search_event_id)
  expect(body.versions.dataset_snapshot).toContain('-sha256:')
  expect(new Set(body.results.map((row) => row.asset.asset_id)).size).toBe(body.results.length)
  const cards = page.getByRole('list', { name: 'Kết quả asset' }).getByRole('listitem')
  await expect(cards).toHaveCount(body.results.length)
  for (const [index, row] of body.results.entries()) {
    await expect(cards.nth(index).getByRole('button', { name: `Xem chi tiết ${row.asset.name}`, exact: true })).toBeVisible()
  }
}

test.beforeEach(async ({ request, page }) => {
  expect((await request.post(process.env.TEXT_SEARCH_CONTROL_URL!, { data: { mode: 'healthy' } })).ok()).toBe(true)
  await page.goto('/')
})

test.afterEach(async ({ request }) => {
  expect((await request.post(process.env.TEXT_SEARCH_CONTROL_URL!, { data: { mode: 'healthy' } })).ok()).toBe(true)
})

test('real retrieval, pagination and detail/back retain search state', async ({ page }, testInfo) => {
  await page.getByLabel('Bạn đang tìm asset nào?').fill('wooden chair')
  const first = await search(page, () => page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click())
  await assertResults(page, await first.json())
  await page.getByRole('combobox', { name: 'Số kết quả', exact: true }).selectOption('6')
  await search(page, () => page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click())
  const second = await search(page, () => page.getByRole('button', { name: 'Trang sau' }).click())
  const body: LiveTextSearchResponse = await second.json()
  expect(body.pagination.page).toBe(2)
  expect(body.pagination.total).toBe(200)
  await assertResults(page, body)
  const row = body.results[0].asset
  const detail = page.waitForResponse(`${process.env.TEXT_SEARCH_API_URL}/api/v1/assets/${row.asset_id}`)
  await page.getByRole('list', { name: 'Kết quả asset' }).getByRole('listitem').first().getByRole('button', { name: `Xem chi tiết ${row.name}`, exact: true }).click()
  expect((await (await detail).json()).asset).toEqual(row)
  await page.getByRole('button', { name: 'Quay lại danh sách' }).click()
  await expect(page.getByLabel('Bạn đang tìm asset nào?')).toHaveValue('wooden chair')
  await expect(page.getByRole('combobox', { name: 'Số kết quả', exact: true })).toHaveValue('6')
  await expect(page.getByRole('navigation', { name: 'Phân trang kết quả' })).toContainText('Trang 2 /')
  await assertResults(page, body)
  await page.screenshot({ path: testInfo.outputPath('real-search-page-2.png'), fullPage: true })
})

test('real AND filters, detail/back and empty results', async ({ page }) => {
  const filters: Record<string, string | number> = JSON.parse(process.env.TEXT_SEARCH_FILTERS!)
  await page.getByLabel('Bạn đang tìm asset nào?').fill('chair')
  await page.locator('summary').filter({ hasText: /^Bộ lọc$/ }).click()
  for (const [key, value] of Object.entries(filters)) {
    await page.locator(`#filter-${key}`).fill(String(value))
  }
  const response = await search(page, () => page.getByRole('button', { name: 'Áp dụng bộ lọc' }).click())
  const body: LiveTextSearchResponse = await response.json()
  expect(response.request().postDataJSON().filters).toEqual(filters)
  expect(body.results.length).toBeGreaterThan(0)
  await assertResults(page, body)
  for (const row of body.results) {
    expect(row.asset.category).toBe(filters.category)
    expect(row.asset.license).toBe(filters.license)
    expect(row.asset.formats).toContain(filters.format)
    expect(row.asset.face_count).toBe(filters.face_count_min)
  }
  await page.getByRole('list', { name: 'Kết quả asset' }).getByRole('listitem').first().getByRole('button', { name: `Xem chi tiết ${body.results[0].asset.name}`, exact: true }).click()
  await page.getByRole('button', { name: 'Quay lại danh sách' }).click()
  await expect(page.locator('#filter-category')).toHaveValue(String(filters.category))
  await page.locator('summary').filter({ hasText: /^Bộ lọc$/ }).click()
  await page.locator('#filter-category').fill('__issue66_no_category__')
  const empty = await search(page, () => page.getByRole('button', { name: 'Áp dụng bộ lọc' }).click())
  expect((await empty.json()).results).toEqual([])
  await expect(page.getByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
})

for (const [mode, status] of [['missing_index', 503], ['db_write_failure', 500]] as const) {
  test(`real ${status} error and retry after server recovery`, async ({ page, request }) => {
    expect((await request.post(process.env.TEXT_SEARCH_CONTROL_URL!, { data: { mode } })).ok()).toBe(true)
    await page.getByLabel('Bạn đang tìm asset nào?').fill('wooden chair')
    const failed = await search(page, () => page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click(), status)
    await expect(page.getByRole('alert')).toContainText('Chưa thể lấy kết quả')
    expect((await failed.json()).error.code).toBeTruthy()
    expect((await request.post(process.env.TEXT_SEARCH_CONTROL_URL!, { data: { mode: 'healthy' } })).ok()).toBe(true)
    const recovered = await search(page, () => page.getByRole('button', { name: 'Thử lại', exact: true }).click())
    expect(recovered.request().postDataJSON()).toEqual(failed.request().postDataJSON())
    await assertResults(page, await recovered.json())
  })
}
