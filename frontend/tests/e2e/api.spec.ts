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

test('browses asset list, handles error/retry, request race, and detail 404/error/broken image while preserving state on return', async ({ page }) => {
  const view = new SearchPage(page)
  const baseAsset = makeResponse('ghế').results[0]!.asset
  let listCalls = 0
  const page1Slow = deferred<void>()

  await page.route('https://example.com/broken-detail.png', (route) => route.fulfill({ status: 404 }))
  await page.route(/\/api\/v1\/assets\?/, async (route) => {
    listCalls++
    const url = new URL(route.request().url())
    const pageNum = Number(url.searchParams.get('page') ?? '1')
    const limitNum = Number(url.searchParams.get('limit') ?? '12')
    const category = url.searchParams.get('category')

    if (listCalls === 1) {
      await route.fulfill({ status: 503, body: 'catalog down' })
      return
    }
    if (category === 'Chậm') {
      await page1Slow.promise
    }
    const assetName = category ? `Asset lọc ${category} trang ${pageNum}` : `Asset trang ${pageNum}`
    const total = limitNum === 2 ? 6 : 1
    const pages = Math.ceil(total / limitNum)
    const count = Math.min(limitNum, Math.max(0, total - (pageNum - 1) * limitNum))
    await route.fulfill({
      json: {
        items: Array.from({ length: count }, (_, idx) => ({
          ...baseAsset,
          asset_id: `asset-p${pageNum}-${idx + 1}`,
          name: idx === 0 ? assetName : `${assetName} (${idx + 1})`,
          category: category ?? 'Nội thất',
        })),
        pagination: { page: pageNum, limit: limitNum, total, pages, has_next: pageNum < pages },
        mock: true,
      },
    })
  })

  let detailCalls = 0
  await page.route('**/api/v1/assets/asset-p*', async (route) => {
    detailCalls++
    if (detailCalls === 1) {
      await route.fulfill({
        status: 404,
        json: { error: { code: 'ASSET_NOT_FOUND', message: 'Asset was not found.', details: { asset_id: 'asset-p2-1' } } },
      })
      return
    }
    if (detailCalls === 2) {
      await route.fulfill({ status: 500, body: 'detail server error' })
      return
    }
    await route.fulfill({
      json: {
        asset: {
          ...baseAsset,
          asset_id: 'asset-p2-1',
          name: 'Chi tiết ghế trang 2',
          thumbnail_url: 'https://example.com/broken-detail.png',
          description: null,
          face_count: null,
          source_url: 'https://example.com/source-p2',
          source: 'Objaverse subset',
        },
        mock: true,
      },
    })
  })

  await view.open()
  await view.browseCatalog()
  await expect(page.getByRole('alert')).toContainText('Dịch vụ asset chưa sẵn sàng')
  await expect(view.results).toHaveCount(0)
  await view.retry()
  await expect(view.catalogRegion).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Asset trang 1', exact: true })).toBeVisible()

  // Apply filter & limit, then navigate to page 2
  await view.chooseLimit('2')
  await view.openApiFilters()
  await page.getByLabel('Danh mục', { exact: true }).fill('Nội thất')
  await view.applyApiFilters()
  await expect(page.getByRole('heading', { name: 'Asset lọc Nội thất trang 1', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Trang sau' }).click()
  await expect(page.getByRole('heading', { name: 'Asset lọc Nội thất trang 2', exact: true })).toBeVisible()
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 3 · 6 kết quả')

  // Open detail -> 404 -> back to list (preserves page 2, limit 2, filter Nội thất)
  await view.openFirstAssetDetail()
  await expect(page.getByRole('heading', { name: 'Không tìm thấy asset' })).toBeVisible()
  await view.backToList()
  await expect(page.getByRole('heading', { name: 'Asset lọc Nội thất trang 2', exact: true })).toBeVisible()
  await expect(page.locator('.search-pagination')).toContainText('Trang 2 / 3 · 6 kết quả')
  await expect(page.getByLabel('Số kết quả')).toHaveValue('2')

  // Open detail -> 500 error -> retry -> success with broken thumbnail & null metadata -> back to list
  await view.openFirstAssetDetail()
  await expect(page.getByRole('heading', { name: 'Chưa thể tải chi tiết asset' })).toBeVisible()
  await view.retry()
  await expect(page.getByRole('heading', { name: 'Chi tiết ghế trang 2', exact: true })).toBeVisible()
  await expect(view.detailRegion.getByText('Chưa có ảnh xem trước')).toBeVisible()
  await expect(view.detailRegion.getByRole('link', { name: 'Objaverse subset' })).toHaveAttribute('href', 'https://example.com/source-p2')
  await view.backToList()
  await expect(page.getByRole('heading', { name: 'Asset lọc Nội thất trang 2', exact: true })).toBeVisible()

  // Request race: trigger slow filter request ("Chậm") then immediately replace with "Nhanh"
  await view.openApiFilters()
  await expect(page.getByLabel('Danh mục', { exact: true })).toHaveValue('Nội thất')
  await page.getByLabel('Danh mục', { exact: true }).fill('Chậm')
  await view.applyApiFilters()
  await expect(view.catalogRegion).toHaveAttribute('aria-busy', 'true')
  await page.getByLabel('Danh mục', { exact: true }).fill('Nhanh')
  await page.locator('#asset-search').evaluate((form) => (form as HTMLFormElement).requestSubmit())
  page1Slow.resolve()
  await expect(page.getByRole('heading', { name: 'Asset lọc Nhanh trang 1', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Asset lọc Chậm trang 1', exact: true })).toHaveCount(0)

  // Reset API filters returns to unfiltered page 1
  await view.resetApiFilters()
  await expect(page.getByRole('heading', { name: 'Asset trang 1', exact: true })).toBeVisible()
  await view.checkWidth()
})
