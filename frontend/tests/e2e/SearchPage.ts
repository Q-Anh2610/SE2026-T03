import { expect, type Page } from '@playwright/test'

export class SearchPage {
  constructor(readonly page: Page) {}
  get query() { return this.page.getByRole('searchbox', { name: 'Bạn đang tìm asset nào?' }) }
  get results() { return this.page.getByRole('list', { name: 'Kết quả asset' }).getByRole('listitem') }
  get gallery() { return this.page.getByRole('region', { name: 'Hình ảnh 3D' }) }
  get resultsRegion() { return this.page.getByRole('region', { name: 'Kết quả tìm kiếm' }) }
  get catalogRegion() { return this.page.getByRole('region', { name: 'Danh sách asset' }) }
  get detailRegion() { return this.page.getByRole('region', { name: 'Chi tiết asset' }) }
  async open() { await this.page.goto('/') }
  async explore() { await this.page.getByRole('navigation', { name: 'Điều hướng chính' }).getByRole('link', { name: 'Khám phá asset' }).click() }
  async toggleTheme() { await this.page.getByRole('button', { name: 'Chế độ tối' }).click() }
  async showAssetDetails() { await this.results.first().getByText('Chi tiết', { exact: true }).click() }
  async browseCatalog() { await this.page.getByRole('button', { name: 'Danh sách asset' }).click() }
  async openFirstAssetDetail() { await this.results.first().getByRole('button', { name: /^Xem chi tiết / }).click() }
  async backToList() { await this.page.getByRole('button', { name: 'Quay lại danh sách' }).first().click() }
  async openApiFilters() { await this.page.getByText('Bộ lọc', { exact: true }).click() }
  async applyApiFilters() { await this.page.getByRole('button', { name: 'Áp dụng bộ lọc' }).click() }
  async resetApiFilters() { await this.page.getByRole('button', { name: 'Đặt lại bộ lọc API' }).click() }
  async search(value: string) { await this.query.fill(value); await this.query.press('Enter') }
  async clearQuery() { await this.page.getByRole('button', { name: 'Xóa truy vấn' }).click() }
  async filter(value: string) { await this.page.getByRole('group', { name: 'Lọc danh mục trong trang' }).getByRole('button', { name: value, exact: true }).click() }
  async clearFilter() { await this.page.getByRole('button', { name: 'Xóa bộ lọc' }).click() }
  async retry() { await this.page.getByRole('button', { name: 'Thử lại' }).click() }
  async chooseLimit(value: string) { await this.page.getByLabel('Số kết quả').selectOption(value) }
  async submitBlank() { await this.page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click() }
  async reset() { await this.page.getByRole('button', { name: 'Xóa tìm kiếm và bộ lọc' }).click() }
  async galleryImages() {
    await this.gallery.scrollIntoViewIfNeeded()
    await this.gallery.getByRole('img').evaluateAll((images) => Promise.all(images.map((image) => (image as HTMLImageElement).decode())))
    return this.gallery.getByRole('img').evaluateAll((images) => images.map((image) => {
      const { x, y, width, height } = image.getBoundingClientRect()
      return { x, y, width, height }
    }))
  }
  async checkWidth() {
    const size = await this.page.evaluate(async () => {
      await document.fonts.ready
      return { page: document.documentElement.scrollWidth, viewport: innerWidth }
    })
    expect(size.page).toBeLessThanOrEqual(size.viewport)
  }
}
