import { expect, test } from '@playwright/test'
import { SearchPage } from './SearchPage'
import { deferred, makeResponse } from '../../src/test/fixtures'

test('keeps HTTP failure visible and retries without mock fallback', async ({ page }) => {
  const view = new SearchPage(page)
  let calls = 0
  await page.route('**/api/v1/search/text', async (route) => {
    calls++
    if (calls === 1) await route.fulfill({ status: 503, body: 'private server details' })
    else await route.fulfill({ json: makeResponse(route.request().postDataJSON().query) })
  })
  await view.open()
  await expect(page.getByLabel('Chế độ dữ liệu')).toHaveCount(0)
  await expect(page.getByText('Thử trạng thái giao diện')).toHaveCount(0)
  await view.search('ghế gỗ')
  await expect(page.getByRole('alert')).toContainText('Dịch vụ tìm kiếm chưa sẵn sàng')
  await expect(view.results).toHaveCount(0)
  await expect(page.getByText('private server details')).toHaveCount(0)
  await view.retry(); await expect(view.results).toHaveCount(1)
  expect(calls).toBe(2)
  await view.checkWidth()
})

test('rejects a malformed API response instead of showing success', async ({ page }) => {
  const view = new SearchPage(page)
  await page.route('**/api/v1/search/text', (route) => route.fulfill({ json: { results: [] } }))
  await view.open(); await view.search('ghế')
  await expect(page.getByRole('alert')).toContainText('không đúng contract')
  await expect(view.results).toHaveCount(0)
})

test('supports null metadata and broken thumbnail while preserving source attribution', async ({ page }) => {
  const view = new SearchPage(page)
  await page.route('https://example.com/preview.png', (route) => route.fulfill({ status: 404 }))
  await page.route('**/api/v1/search/text', (route) => {
    const response = makeResponse(route.request().postDataJSON().query)
    Object.assign(response.results[0].asset, { category: null, description: null, thumbnail_url: 'https://example.com/preview.png', source_url: 'https://example.com/asset', source: 'Test source' })
    return route.fulfill({ json: response })
  })
  await view.open(); await view.search('ghế')
  await expect(view.results).toHaveCount(1)
  await expect(page.getByText('Chưa có thông tin', { exact: true })).toHaveCount(3)
  await expect(page.getByText('Chưa có ảnh xem trước')).toBeVisible()
  await view.showAssetDetails()
  await expect(page.getByRole('link', { name: 'Test source' })).toHaveAttribute('rel', 'noopener noreferrer')
  await view.checkWidth()
})

test('keeps preview images aligned from loading to results and records the UI', async ({ page }, testInfo) => {
  const view = new SearchPage(page)
  const pending = deferred<void>()
  const illustrations = [
    ['chair', 'Ghế gỗ'], ['lamp', 'Đèn bàn'], ['vase', 'Bình gốm'],
    ['stool', 'Ghế chrome'], ['arch', 'Kiến trúc'], ['plant', 'Cây cảnh'],
  ]
  await page.route('**/api/v1/search/text', async (route) => {
    await pending.promise
    const response = makeResponse(route.request().postDataJSON().query)
    const template = response.results[0]
    response.results = illustrations.map(([file, name], index) => ({
      ...template,
      rank: index + 1,
      asset: { ...template.asset, asset_id: `ui-fixture-${file}`, name, thumbnail_url: new URL(`/images/discovery/${file}.webp`, page.url()).href },
    }))
    response.pagination.total = response.results.length
    await route.fulfill({ json: response })
  })
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
  await view.open()
  await view.search('glb')
  await expect(view.resultsRegion).toHaveAttribute('aria-busy', 'true')
  await expect(page.getByRole('button', { name: 'Đang tìm…' })).toBeDisabled()
  await expect(view.gallery).toHaveCount(0)
  await expect(view.results).toHaveCount(0)
  await view.resultsRegion.screenshot({ path: testInfo.outputPath('loading.png') })
  pending.resolve()
  await expect(view.results).toHaveCount(6)
  await expect(view.resultsRegion).toHaveAttribute('aria-busy', 'false')
  await view.results.getByRole('img').evaluateAll((images) => Promise.all(images.map((image) => (image as HTMLImageElement).decode())))
  const previews = await view.results.locator('.asset-preview').evaluateAll((elements) => elements.map((element) => {
    const { width, height } = element.getBoundingClientRect()
    return { width, height }
  }))
  for (const preview of previews) expect(Math.abs(preview.width - preview.height)).toBeLessThan(1)
  await view.resultsRegion.screenshot({ path: testInfo.outputPath('results-images-light.png') })
  await view.toggleTheme()
  await view.resultsRegion.screenshot({ path: testInfo.outputPath('results-images-dark.png') })
  await view.checkWidth()
})
