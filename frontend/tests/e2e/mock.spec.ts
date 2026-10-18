import { expect, test } from '@playwright/test'
import { SearchPage } from './SearchPage'

test('preserves the query and results when switching themes and restores the saved choice', async ({ page }) => {
  const view = new SearchPage(page)
  await page.emulateMedia({ colorScheme: 'light' })
  await view.open()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await view.search('glb')
  await expect(view.results).toHaveCount(6)
  await view.toggleTheme()
  await expect(page.getByRole('button', { name: 'Chế độ tối' })).toHaveAttribute('aria-pressed', 'true')
  await expect(view.query).toHaveValue('glb')
  await expect(view.results).toHaveCount(6)
  await view.checkWidth()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await view.explore()
  await view.search('ghe go')
  await expect(view.results).toHaveCount(1)
  await view.toggleTheme()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(view.results).toHaveCount(1)
  await view.checkWidth()
})

test('searches by Enter and returns focus after clearing', async ({ page }) => {
  const view = new SearchPage(page)
  await view.open()
  await expect(page.getByLabel('Chế độ dữ liệu')).toHaveCount(0)
  await expect(page.getByText('Bản mẫu tuần 1')).toHaveCount(0)
  await expect(page.locator('.site-title')).toHaveText('Thư viện 3D')
  await expect(page.getByRole('region', { name: 'Kết quả tìm kiếm' })).toHaveCount(0)
  const heroImage = page.locator('.hero-landscape')
  await expect.poll(() => heroImage.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  const centered = await page.locator('.search-panel').evaluate((panel) => {
    const bounds = panel.getBoundingClientRect()
    const gallery = document.querySelector('.discovery-gallery')!.getBoundingClientRect()
    return {
      horizontal: Math.abs(bounds.x + bounds.width / 2 - innerWidth / 2),
      vertical: Math.abs(bounds.y + bounds.height / 2 - innerHeight / 2),
      galleryTop: gallery.top,
      viewport: innerHeight,
    }
  })
  expect(centered.horizontal).toBeLessThanOrEqual(2)
  expect(centered.vertical).toBeLessThanOrEqual(2)
  expect(centered.galleryTop).toBeGreaterThanOrEqual(centered.viewport)
  const gallery = page.getByRole('region', { name: 'Hình ảnh 3D' })
  await expect(gallery.getByRole('img')).toHaveCount(6)
  for (const img of await gallery.getByRole('img').all()) {
    await img.scrollIntoViewIfNeeded()
    await expect(img).toBeVisible()
    await expect.poll(() => img.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  }
  await view.checkWidth()
  await view.explore()
  await expect(page).toHaveURL(/#search-panel$/)
  await expect(view.query).toBeInViewport()
  await view.search('ghe go')
  await expect(gallery).toHaveCount(0)
  await expect(view.results).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Ghế gỗ đơn giản' })).toBeVisible()
  await expect(page.getByText('Nguồn truy xuất: mock_metadata')).toBeHidden()
  await view.showAssetDetails()
  await expect(page.getByText('Nguồn truy xuất: mock_metadata')).toBeVisible()
  await view.clearQuery()
  await expect(gallery).toBeVisible()
  await expect(page.getByRole('region', { name: 'Kết quả tìm kiếm' })).toHaveCount(0)
  await expect(view.query).toBeFocused()
  await expect(view.query).toHaveValue('')
  await view.checkWidth()
})

test('moves the background on scroll and respects reduced motion', async ({ page }) => {
  const view = new SearchPage(page)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await view.open()
  await page.evaluate(() => window.scrollTo({ top: 240, behavior: 'instant' }))
  const background = page.locator('.hero-landscape')
  await expect.poll(() => background.evaluate((element) => new DOMMatrixReadOnly(getComputedStyle(element).transform).m42)).toBeGreaterThan(0)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(background).toHaveCSS('transform', 'none')
  await expect(page.locator('.hero-water-light')).toBeHidden()
  await view.checkWidth()
})

for (const theme of ['light', 'dark'] as const) {
  test(`keeps gallery rows aligned and records the ${theme} UI for review`, async ({ page }, testInfo) => {
    const view = new SearchPage(page)
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    await view.open()
    const images = await view.galleryImages()
    expect(images).toHaveLength(6)
    const mobile = (page.viewportSize()?.width ?? 0) <= 700
    for (const image of images) {
      expect(Math.abs(image.width - image.height)).toBeLessThan(1)
      expect(Math.abs(image.width - images[0].width)).toBeLessThan(1)
    }
    if (mobile) {
      expect(images[0].x).toBeLessThanOrEqual(16)
      for (const image of images) expect(Math.abs(image.x - images[0].x)).toBeLessThan(1)
    } else {
      expect(images[0].x).toBeLessThanOrEqual(24)
      for (let index = 0; index < images.length; index += 2) {
        expect(Math.abs(images[index].y - images[index + 1].y)).toBeLessThan(1)
      }
    }
    const captionsFit = await view.gallery.locator('figcaption').evaluateAll((captions) => captions.every((caption) => caption.scrollWidth <= caption.clientWidth))
    expect(captionsFit).toBe(true)
    await view.checkWidth()
    await view.gallery.screenshot({ path: testInfo.outputPath(`gallery-${theme}.png`), style: ".site-header, .skip-link { visibility: hidden !important; }" })
  })

  test(`keeps search results aligned and usable in ${theme} theme`, async ({ page }, testInfo) => {
    const view = new SearchPage(page)
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    await view.open()
    await view.search('glb')
    await expect(view.results).toHaveCount(6)
    await expect(page.locator('.results-summary')).toMatchAriaSnapshot(`
      - heading "Kết quả tìm kiếm" [level=2]
      - paragraph: 6 / 6 asset trong kết quả
    `)
    const layout = await view.results.evaluateAll((cards) => cards.map((card) => {
      const preview = card.querySelector('.asset-preview')!.getBoundingClientRect()
      const title = card.querySelector('h3')!.getBoundingClientRect()
      return { x: preview.x, y: preview.y, width: preview.width, height: preview.height, titleY: title.y }
    }))
    const width = page.viewportSize()!.width
    const columns = width <= 700 ? 1 : width <= 1000 ? 2 : 3
    for (const card of layout) {
      expect(Math.abs(card.width - card.height)).toBeLessThan(1)
      expect(Math.abs(card.width - layout[0].width)).toBeLessThan(1)
    }
    for (let index = 1; index < columns; index++) {
      expect(Math.abs(layout[index].y - layout[0].y)).toBeLessThan(1)
      expect(Math.abs(layout[index].titleY - layout[0].titleY)).toBeLessThan(1)
    }
    await view.chooseLimit('6')
    await expect(page.getByLabel('Số kết quả')).toHaveValue('6')
    await view.checkWidth()
    await view.resultsRegion.screenshot({ path: testInfo.outputPath(`results-${theme}.png`) })
    await view.showAssetDetails()
    await expect(view.results.first().getByText('Dữ liệu minh họa tự tạo')).toBeVisible()
    await view.filter('Nội thất')
    await expect(view.results).toHaveCount(3)
    await expect(page.locator('.results-summary')).toContainText('3 / 6')
    await view.clearQuery()
    await expect(view.gallery).toBeVisible()
    await expect(view.query).toBeFocused()
    await view.checkWidth()
  })
}

test('validates blank searches without removing the gallery', async ({ page }) => {
  const view = new SearchPage(page)
  await view.open()
  await view.submitBlank()
  await expect(page.getByRole('alert')).toContainText('1 đến 500')
  await expect(view.query).toBeFocused()
  await expect(view.gallery).toBeVisible()
  await expect(view.resultsRegion).toHaveCount(0)
})

test('shows the active filter and clears it independently of query', async ({ page }) => {
  const view = new SearchPage(page)
  await view.open(); await view.search('glb')
  await expect(view.results).toHaveCount(6)
  await view.filter('Nội thất')
  await expect(view.results).toHaveCount(3)
  await expect(page.getByText(/Đang lọc:/)).toContainText('Nội thất')
  await view.clearQuery()
  await expect(page.getByText(/Đang lọc:/)).toBeVisible()
  await view.clearFilter()
  await expect(view.query).toBeFocused()
  await expect(page.getByText(/Đang lọc:/)).toHaveCount(0)
  await view.checkWidth()
})

test('keeps search compact and resets a genuine empty result', async ({ page }) => {
  const view = new SearchPage(page)
  await view.open()
  await expect(page.getByText('Thử với', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Thử trạng thái giao diện')).toHaveCount(0)
  await expect(view.query).not.toHaveAttribute('aria-describedby')
  const bounds = await page.locator('.search-panel').boundingBox()
  expect(bounds?.width).toBeLessThanOrEqual(760)
  await view.search('glb')
  await expect(view.results).toHaveCount(6)
  const limitSpacing = await page.locator('.limit-label').evaluate((label) => {
    const select = label.querySelector('select')!
    return {
      arrowInset: parseFloat(getComputedStyle(label, '::after').right),
      textInset: parseFloat(getComputedStyle(select).paddingRight),
    }
  })
  expect(limitSpacing.arrowInset).toBeGreaterThanOrEqual(16)
  expect(limitSpacing.textInset).toBeGreaterThanOrEqual(40)
  for (const value of ['6', '12', '24']) {
    const limit = page.getByLabel('Số kết quả')
    await limit.selectOption(value)
    await expect(limit).toHaveValue(value)
    const textFits = await limit.evaluate((element) => {
      const select = element as HTMLSelectElement
      const style = getComputedStyle(select)
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')!
      context.font = style.font
      const textWidth = context.measureText(select.selectedOptions[0].text).width
      const availableWidth = select.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
      return textWidth <= availableWidth
    })
    expect(textFits).toBe(true)
  }
  await view.search('không tồn tại')
  await expect(page.getByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: 'Xóa tìm kiếm và bộ lọc' }).click()
  await expect(view.query).toHaveValue('')
  await expect(view.query).toBeFocused()
  await view.checkWidth()
})
