import { expect, test as base, type Locator, type Page, type Response } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, resolve, sep } from 'node:path'
import type { AssetFilters, LiveSearchResponse } from '../../src/features/search/types'

interface SuiteInput {
  query_image: string
  query_sha256: string
  asset_count: number
  text_versions: LiveSearchResponse['versions']
  image_versions: LiveSearchResponse['versions']
  filters: Required<AssetFilters>
}
const inputPath = resolve(process.env.E2E_STACK_INPUT!)
const input: SuiteInput = JSON.parse(readFileSync(inputPath, 'utf8'))
const imagePath = resolve(dirname(inputPath), input.query_image)
if (!imagePath.startsWith(dirname(inputPath) + sep)) throw new Error('Ảnh phải nằm trong gói input E2E.')
const bytes = readFileSync(imagePath)
if (createHash('sha256').update(bytes).digest('hex') !== input.query_sha256) throw new Error('Query image checksum mismatch.')

// Chỉ quan sát HTTP của stack thật; không route.fulfill, mock encoder hay control endpoint.
const test = base.extend<{ evidence: void }>({
  evidence: [async ({ page }, use, testInfo) => {
    const observations: unknown[] = []
    const pending: Promise<void>[] = []
    page.on('response', response => {
      const url = new URL(response.url())
      if (url.origin !== new URL(process.env.E2E_STACK_URL!).origin
        || (!url.pathname.startsWith('/api/v1/') && url.pathname !== '/openapi.json')) return
      pending.push((async () => {
        const json: Record<string, unknown> | null = await response.json().catch(() => null)
        observations.push({ path: url.pathname, method: response.request().method(), status: response.status(),
          content_type: response.headers()['content-type'],
          body: url.pathname === '/openapi.json' ? { feedback_schema: feedbackSchema(json) } : json })
      })())
    })
    page.on('requestfailed', request => {
      const url = new URL(request.url())
      if (url.origin === new URL(process.env.E2E_STACK_URL!).origin && url.pathname.startsWith('/api/v1/')) {
        observations.push({ path: url.pathname, method: request.method(), failure: request.failure()?.errorText })
      }
    })
    await use()
    await Promise.all(pending)
    await testInfo.attach('stack-http-observations', { body: JSON.stringify(observations), contentType: 'application/json' })
  }, { auto: true }],
})

function feedbackSchema(spec: Record<string, unknown> | null): string | undefined {
  const value = spec as { paths?: Record<string, { post?: { responses?: Record<string, {
    content?: Record<string, { schema?: { $ref?: string } }>
  }> } }> } | null
  return value?.paths?.['/api/v1/feedback']?.post?.responses?.['201']?.content?.['application/json']?.schema?.$ref
}

async function search(page: Page, kind: 'text' | 'image', action: () => Promise<unknown>) {
  const path = `/api/v1/search/${kind}`
  const response = Promise.race([
    page.waitForResponse(item => new URL(item.url()).pathname === path && item.request().method() === 'POST'),
    page.waitForEvent('requestfailed', { predicate: item => new URL(item.url()).pathname === path })
      .then(item => { throw new Error(`${path}: request failed (${item.failure()?.errorText})`) }),
  ])
  await action()
  const received = await response
  expect(received.status()).toBe(200)
  const body: LiveSearchResponse = await received.json()
  expect(body.mock).toBe(false)
  expect(body.query_id).toBe(body.search_event_id)
  expect(body.versions).toEqual(kind === 'text' ? input.text_versions : input.image_versions)
  expect(body.pagination.total).toBeLessThanOrEqual(200)
  expect(new Set(body.results.map(row => row.asset.asset_id)).size).toBe(body.results.length)
  expect(body.results.map(row => row.rank)).toEqual(body.results.map((_, index) => index + 1))
  for (const [index, row] of body.results.entries()) {
    expect(row.retrieval_sources).toEqual([kind === 'text' ? 'clip_text_to_preview' : 'clip_image_to_preview'])
    expect(row.score_type).toBe('cosine')
    expect(row.score).toBeGreaterThanOrEqual(-1)
    expect(row.score).toBeLessThanOrEqual(1)
    expect(row.explanation.trim().length).toBeGreaterThan(0)
    if (index) expect(body.results[index - 1].score! + 1e-6).toBeGreaterThanOrEqual(row.score!)
  }
  return body
}

function cards(page: Page, kind: 'text' | 'image') {
  return page.getByRole('list', { name: kind === 'text' ? 'Kết quả asset' : 'Kết quả ảnh', exact: true }).getByRole('listitem')
}

async function assertCards(list: Locator, body: LiveSearchResponse) {
  await expect(list).toHaveCount(body.results.length)
  for (const [index, row] of body.results.entries()) {
    await expect(list.nth(index).getByRole('button', { name: `Xem chi tiết ${row.asset.name}`, exact: true })).toBeVisible()
  }
}

async function textSearch(page: Page) {
  await page.goto('/')
  await page.getByLabel('Bạn đang tìm asset nào?').fill('wooden chair')
  return search(page, 'text', () => page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click())
}

async function imageSearch(page: Page) {
  await page.goto('/#image-search')
  await page.getByLabel(/Chọn hoặc thay ảnh/).setInputFiles({ name: 'query.jpg', mimeType: 'image/jpeg', buffer: bytes })
  await expect(page.getByRole('img', { name: 'Ảnh truy vấn: query.jpg' })).toBeVisible()
  const body = await search(page, 'image', () => page.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click())
  expect(body.query).toBe(`sha256:${input.query_sha256}`)
  return body
}

async function detailAndBack(page: Page, kind: 'text' | 'image', body: LiveSearchResponse) {
  const asset = body.results[0].asset
  const pending = page.waitForResponse(item => new URL(item.url()).pathname === `/api/v1/assets/${asset.asset_id}`)
  await cards(page, kind).first().getByRole('button', { name: `Xem chi tiết ${asset.name}`, exact: true }).click()
  const detail = await pending
  expect(detail.status()).toBe(200)
  expect(await detail.json()).toMatchObject({ asset, mock: false })
  await expect(page.getByRole('region', { name: 'Chi tiết asset' })).toBeVisible()
  await page.getByRole('button', { name: 'Quay lại danh sách', exact: true }).click()
  await assertCards(cards(page, kind), body)
}

function assertFilters(body: LiveSearchResponse) {
  expect(body.results.length).toBeGreaterThan(0)
  for (const { asset } of body.results) {
    expect(asset.category).toBe(input.filters.category)
    expect(asset.license).toBe(input.filters.license)
    expect(asset.formats).toContain(input.filters.format)
    expect(asset.face_count).toBe(input.filters.face_count_min)
  }
}

test('nginx exposes the live feedback OpenAPI contract', async ({ request }) => {
  const health = await request.get('/healthz')
  expect(health.status()).toBe(200)
  const response = await request.get('/openapi.json')
  expect(response.status()).toBe(200)
  expect(response.headers()['content-type']).toContain('application/json')
  expect(feedbackSchema(await response.json())).toBe('#/components/schemas/LiveFeedbackResponse')
})

test('text retrieval, pagination, detail and back use real metadata', async ({ page }) => {
  const first = await textSearch(page)
  expect(first.pagination.total).toBe(input.asset_count)
  await assertCards(cards(page, 'text'), first)
  const second = await search(page, 'text', () => page.getByRole('button', { name: 'Trang sau', exact: true }).click())
  expect(second.pagination.page).toBe(2)
  expect(second.search_event_id).not.toBe(first.search_event_id)
  expect(second.results.every(row => !first.results.some(old => old.asset.asset_id === row.asset.asset_id))).toBe(true)
  await detailAndBack(page, 'text', second)
  await expect(page.getByLabel('Bạn đang tìm asset nào?')).toHaveValue('wooden chair')
  await expect(page.getByRole('navigation', { name: 'Phân trang kết quả' })).toContainText('Trang 2')
})

test('text AND filters and empty state', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Bạn đang tìm asset nào?').fill('chair')
  await page.locator('summary').filter({ hasText: /^Bộ lọc$/ }).click()
  for (const [key, value] of Object.entries(input.filters)) await page.locator(`#filter-${key}`).fill(String(value))
  const filtered = await search(page, 'text', () => page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click())
  assertFilters(filtered)
  await detailAndBack(page, 'text', filtered)
  // Disclosure state may be restored closed after leaving the detail view.
  if (!(await page.locator('#filter-category').isVisible())) await page.locator('summary').filter({ hasText: /^Bộ lọc$/ }).click()
  await page.locator('#filter-category').fill('__issue149_no_category__')
  const empty = await search(page, 'text', () => page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click())
  expect(empty.results).toEqual([])
  expect(empty.pagination.total).toBe(0)
  await expect(page.getByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
})

test('image retrieval, pagination, detail and back retain the image', async ({ page }) => {
  const first = await imageSearch(page)
  expect(first.pagination.total).toBe(input.asset_count)
  await assertCards(cards(page, 'image'), first)
  const second = await search(page, 'image', () => page.getByRole('button', { name: 'Trang sau', exact: true }).click())
  expect(second.pagination.page).toBe(2)
  expect(second.results.every(row => !first.results.some(old => old.asset.asset_id === row.asset.asset_id))).toBe(true)
  await detailAndBack(page, 'image', second)
  await expect(page.getByRole('img', { name: 'Ảnh truy vấn: query.jpg' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Phân trang ảnh' })).toContainText('Trang 2')
})

test('image AND filters and empty state', async ({ page }) => {
  await imageSearch(page)
  const labels = { category: 'Danh mục', license: 'License', format: 'Định dạng', face_count_min: 'Số mặt tối thiểu', face_count_max: 'Số mặt tối đa' }
  for (const [key, label] of Object.entries(labels)) await page.getByLabel(label, { exact: true }).fill(String(input.filters[key as keyof AssetFilters]))
  const filtered = await search(page, 'image', () => page.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click())
  assertFilters(filtered)
  await detailAndBack(page, 'image', filtered)
  await page.getByLabel('Danh mục', { exact: true }).fill('__issue149_no_category__')
  const empty = await search(page, 'image', () => page.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click())
  expect(empty.results).toEqual([])
  expect(empty.pagination.total).toBe(0)
  await expect(page.getByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
})

for (const kind of ['text', 'image'] as const) {
  test(`${kind} UI feedback is accepted by PostgreSQL mode`, async ({ page }) => {
    const body = await (kind === 'text' ? textSearch(page) : imageSearch(page))
    const first = cards(page, kind).first()
    // Start listening before click; keep the failed contract/UI assertion visible.
    let saved: Response | undefined
    page.on('response', response => { if (new URL(response.url()).pathname === '/api/v1/feedback') saved = response })
    await first.getByRole('button', { name: 'Phù hợp', exact: true }).click()
    await expect(first.getByRole('status')).toHaveText('Đã lưu đánh giá.')
    expect(saved).toBeDefined()
    expect(saved!.status()).toBe(201)
    expect(await saved!.json()).toMatchObject({ search_event_id: body.search_event_id,
      asset_id: body.results[0].asset.asset_id, relevance: true, storage: 'postgresql', mock: false })
  })
}

test('direct API feedback and invalid input use real endpoints', async ({ request }, testInfo) => {
  const response = await request.post('/api/v1/search/text', { data: { query: 'chair', filters: {}, page: 1, limit: 6 } })
  expect(response.status()).toBe(200)
  const body: LiveSearchResponse = await response.json()
  expect(body.mock).toBe(false)
  const feedback = await request.post('/api/v1/feedback', { data: { search_event_id: body.search_event_id,
    asset_id: body.results[0].asset.asset_id, relevance: false } })
  expect(feedback.status()).toBe(201)
  const saved = await feedback.json()
  expect(saved).toMatchObject({ search_event_id: body.search_event_id, asset_id: body.results[0].asset.asset_id,
    relevance: false, storage: 'postgresql', mock: false })
  await testInfo.attach('direct-feedback-receipt', { body: JSON.stringify(saved), contentType: 'application/json' })
  const invalid = await request.post('/api/v1/search/text', { data: { query: 'chair', filters: {}, limit: 0 } })
  expect(invalid.status()).toBe(400)
  const corrupt = await request.post('/api/v1/search/image', { multipart: { image: { name: 'broken.png', mimeType: 'image/png', buffer: Buffer.from('invalid image') } } })
  expect(corrupt.status()).toBe(400)
})
