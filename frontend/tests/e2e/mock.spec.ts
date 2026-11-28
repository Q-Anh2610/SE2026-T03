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
  await expect(view.query).toHaveValue('glb')
  await expect(view.results).toHaveCount(6)
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
  const heroImages = page.locator('.hero-showcase img')
  await expect(heroImages).toHaveCount(2)
  await expect.poll(() => heroImages.evaluateAll((images) =>
    images.every((image) => (image as HTMLImageElement).naturalWidth > 0))).toBe(true)
  const gallery = view.gallery
  await expect(gallery.locator('img')).toHaveCount(4)
  for (const img of await gallery.locator('img').all()) {
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
  await expect(page.getByText('Metadata · mock')).toBeVisible()
  await view.showAssetDetails()
  await view.clearQuery()
  await expect(gallery).toBeVisible()
  await expect(page.getByRole('region', { name: 'Kết quả tìm kiếm' })).toHaveCount(0)
  await expect(view.query).toBeFocused()
  await expect(view.query).toHaveValue('')
  await view.checkWidth()
})

test('uses a discovery suggestion with the keyboard and respects reduced motion', async ({ page }) => {
  const view = new SearchPage(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await view.open()
  const suggestion = view.gallery.getByRole('button', { name: 'Điền gợi ý tìm kiếm: Ghế gỗ' })
  await expect(suggestion).toHaveCSS('transition-duration', '0s')
  await suggestion.focus()
  await page.keyboard.press('Enter')
  await expect(view.query).toBeFocused()
  await expect(view.query).toHaveValue('Ghế gỗ')
  await page.keyboard.press('Enter')
  await expect(view.results).toHaveCount(1)
  await view.checkWidth()
})

for (const theme of ['light', 'dark'] as const) {
  test(`keeps gallery rows aligned and records the ${theme} UI for review`, async ({ page }, testInfo) => {
    const view = new SearchPage(page)
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    await view.open()
    const images = await view.galleryImages()
    expect(images).toHaveLength(4)
    for (const image of images) {
      expect(image.width / image.height).toBeGreaterThan(1)
      expect(Math.abs(image.width - images[0].width)).toBeLessThan(1)
    }
    for (let index = 0; index < images.length; index += 2) {
      expect(Math.abs(images[index].y - images[index + 1].y)).toBeLessThan(1)
      expect(images[index + 1].x).toBeGreaterThan(images[index].x)
      expect(Math.abs(images[index].x - images[0].x)).toBeLessThan(1)
    }
    const captionsFit = await view.gallery.locator('.discovery-tile-copy').evaluateAll((captions) => captions.every((caption) => caption.scrollWidth <= caption.clientWidth))
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
      expect(Math.abs(card.width * 3 / 4 - card.height)).toBeLessThan(1)
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
  await expect(view.query).toBeInViewport()
  await view.checkWidth()
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

test('preserves search results and the draft across anchor navigation and browser history', async ({ page }) => {
  const view = new SearchPage(page)
  await view.open()
  await view.search('ghe go')
  await expect(view.results).toHaveCount(1)
  await view.query.fill('bản nháp chưa gửi')

  await page.getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Khám phá asset' }).click()
  await expect(page).toHaveURL(/#search-panel$/)
  await expect(view.query).toHaveValue('bản nháp chưa gửi')
  await expect(view.results).toHaveCount(1)

  await page.goBack()
  await expect(view.query).toHaveValue('bản nháp chưa gửi')
  await expect(view.results).toHaveCount(1)
  await page.goForward()
  await expect(page).toHaveURL(/#search-panel$/)
  await expect(view.query).toHaveValue('bản nháp chưa gửi')
  await expect(view.results).toHaveCount(1)
})

test('skips navigation with the keyboard without leaving image search', async ({ page }) => {
  await page.goto('/#image-search')
  const main = page.getByRole('main')
  const imageInput = main.getByLabel(/Chọn hoặc thay ảnh JPEG\/PNG/)
  await expect(imageInput).toHaveCount(1)

  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Đến nội dung chính' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(main).toBeFocused()
  await expect(page).toHaveURL(/#image-search$/)

  await page.keyboard.press('Tab')
  await expect(imageInput).toBeFocused()
  await expect(page.locator('.image-file-drop')).toHaveCSS('outline-style', 'solid')
})

test('fits search results and image filters at 320 CSS pixels', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  const view = new SearchPage(page)
  await view.open()
  await view.search('glb')
  await expect(view.results).toHaveCount(6)
  await view.checkWidth()

  await page.getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Tìm bằng ảnh' }).click()
  await expect(page.getByRole('group', { name: 'Bộ lọc ảnh' })).toBeVisible()
  await view.checkWidth()
})
