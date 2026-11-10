import { expect, test } from '@playwright/test'
import { makeLiveResponse } from '../../src/test/fixtures'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

const live = !!process.env.IMAGE_SMOKE_API_URL
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nO8AAAAASUVORK5CYII=', 'base64')

test('image upload, filters, pagination, detail/back and execution metadata', async ({ page }) => {
  const bytes = live ? readFileSync(process.env.IMAGE_SMOKE_QUERY!) : png
  const reference = `sha256:${createHash('sha256').update(bytes).digest('hex')}`
  if (!live) {
    await page.route('**/api/v1/search/image', async route => {
      const request = route.request().postDataBuffer()!.toString()
      expect(request).toContain('name="image"')
      expect(request).toContain('name="filters"')
      const response = makeLiveResponse(reference)
      response.results[0].retrieval_sources = ['clip_image_to_preview']
      if (request.includes('__empty__')) { response.results = []; response.pagination = { page: 1, limit: 12, total: 0, pages: 0, has_next: false } }
      await route.fulfill({ json: response })
    })
    await page.route('**/api/v1/assets/*', route => route.fulfill({ json: { asset: makeLiveResponse().results[0].asset, mock: false } }))
  }
  const responses: unknown[] = []
  page.on('response', async response => {
    if (response.url().endsWith('/api/v1/search/image') && response.status() === 200) responses.push(await response.json())
  })
  await page.goto('/#image-search')
  await page.getByLabel(/Chọn hoặc thay ảnh/).setInputFiles({ name: 'query.png', mimeType: 'image/png', buffer: bytes })
  await expect(page.getByRole('img', { name: 'Ảnh truy vấn: query.png' })).toBeVisible()
  await page.getByLabel('Định dạng', { exact: true }).fill('glb')
  await page.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click()
  await expect(page.getByText('Kết quả tìm kiếm bằng ảnh', { exact: true })).toBeVisible()
  await page.getByText('Thông tin phiên tìm ảnh').click()
  await expect(page.getByText(reference, { exact: true })).toBeVisible()
  if (live) {
    await expect.poll(() => responses.length).toBeGreaterThan(0)
    const firstResult = responses[0] as { search_event_id: string; results: Array<{ asset: { asset_id: string } }> }
    const firstCard = page.locator('.asset-grid > li').first()
    const feedbackResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/feedback') && response.request().method() === 'POST')
    await firstCard.getByRole('button', { name: 'Phù hợp', exact: true }).click()
    const saved = await feedbackResponse
    expect(saved.status()).toBe(201)
    const feedback = await saved.json()
    expect(feedback).toMatchObject({ search_event_id: firstResult.search_event_id, asset_id: firstResult.results[0].asset.asset_id, relevance: true, storage: 'postgresql', mock: false })
    await expect(firstCard.getByRole('status')).toHaveText('Đã lưu đánh giá.')
    await test.info().attach('live-feedback-response', { body: JSON.stringify(feedback), contentType: 'application/json' })
    await page.getByRole('button', { name: 'Trang sau' }).click()
    await expect(page.getByText(/Trang 2/)).toBeVisible()
  }
  await page.getByRole('button', { name: /Xem chi tiết/ }).first().click()
  await expect(page.getByRole('region', { name: 'Chi tiết asset' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Chi tiết asset' }).getByRole('heading')).toBeVisible()
  await page.getByRole('button', { name: 'Quay lại danh sách', exact: true }).click()
  await expect(page.getByRole('img', { name: 'Ảnh truy vấn: query.png' })).toBeVisible()
  if (live) await expect(page.getByText(/Trang 2/)).toBeVisible()
  await page.getByLabel('Danh mục', { exact: true }).fill('__empty__')
  await page.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click()
  await expect(page.getByText('Chưa có asset phù hợp')).toBeVisible()
  await expect(page.getByText(/Trang 1/)).toBeVisible()
  expect(responses.length).toBeGreaterThanOrEqual(2)
  for (const body of responses as ReturnType<typeof makeLiveResponse>[]) {
    expect(body.query).toBe(reference)
    expect(body.mock).toBe(false)
    expect(body.query_id).toBe(body.search_event_id)
    for (const result of body.results) expect(result.asset.formats).toContain('glb')
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await test.info().attach('image-http-responses', { body: JSON.stringify(responses), contentType: 'application/json' })
})

test('upload validation and HTTP error/retry keep the selected image', async ({ page }) => {
  test.skip(live, 'Fault injection is covered separately by the real HTTP verifier.')
  let calls = 0
  await page.route('**/api/v1/search/image', async route => {
    calls++
    if (calls === 1) return route.fulfill({ status: 503, json: { error: { code: 'SEARCH_UNAVAILABLE', message: 'private' } } })
    const response = makeLiveResponse(`sha256:${'a'.repeat(64)}`)
    response.results[0].retrieval_sources = ['clip_image_to_preview']
    await route.fulfill({ json: response })
  })
  await page.goto('/#image-search')
  const input = page.getByLabel(/Chọn hoặc thay ảnh/)
  await input.setInputFiles({ name: 'bad.png', mimeType: 'image/png', buffer: Buffer.from('invalid') })
  await expect(page.getByRole('alert')).toBeVisible()
  expect(calls).toBe(0)
  await input.setInputFiles({ name: 'query.png', mimeType: 'image/png', buffer: png })
  await expect(page.getByRole('img')).toBeVisible()
  await page.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('chưa sẵn sàng')
  await expect(page.getByRole('list', { name: 'Kết quả ảnh' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Thử lại', exact: true }).click()
  await expect(page.getByRole('list', { name: 'Kết quả ảnh' })).toBeVisible()
})
