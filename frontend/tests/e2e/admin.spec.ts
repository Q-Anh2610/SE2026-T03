import { expect, test } from '@playwright/test'
import { deferred } from '../../src/test/fixtures'
import type { JobMetadata } from '../../src/features/admin/types'

// HTTP interception only. This key and these jobs are test fixtures, not live data.
const KEY = 'e2e-admin-key-103-not-a-real-secret'

function makeJob(index: number): JobMetadata {
  const failed = index === 0
  const indexing = index === 12
  return {
    job_id: `a0b674d2-1286-401f-b73b-${String(index + 1).padStart(12, '0')}`,
    kind: indexing ? 'indexing' : 'ingestion',
    runner: indexing ? 'prepare_text_search_index' : 'ingestion.run_batch',
    status: failed ? 'failed' : 'succeeded',
    created_at: '2026-11-14T08:00:00Z',
    updated_at: '2026-11-14T08:01:00Z',
    started_at: '2026-11-14T08:00:01Z',
    finished_at: '2026-11-14T08:01:00Z',
    progress: {
      unit: 'assets',
      processed: indexing ? null : 1,
      total: indexing ? null : 1,
      percent: indexing ? null : 100,
    },
    result: {
      persistence: indexing ? null : 'postgresql',
      input_count: indexing ? null : 1,
      succeeded: indexing ? null : failed ? 0 : 1,
      failed: indexing ? null : failed ? 1 : 0,
      skipped: indexing ? null : 0,
      manifest_sha256: indexing ? null : 'a'.repeat(64),
      exit_code: indexing ? 0 : null,
    },
    error: failed
      ? { code: 'BATCH_PARTIAL_FAILURE', message: 'Có asset xử lý thất bại.' }
      : null,
  }
}

function listBody(url: URL, jobs: JobMetadata[]) {
  const filtered = jobs.filter(job => (
    (!url.searchParams.has('kind') || job.kind === url.searchParams.get('kind'))
    && (!url.searchParams.has('status') || job.status === url.searchParams.get('status'))
  ))
  const page = Number(url.searchParams.get('page'))
  const limit = Number(url.searchParams.get('limit'))
  const pages = Math.ceil(filtered.length / limit)
  return {
    items: filtered.slice((page - 1) * limit, page * limit),
    pagination: { page, limit, total: filtered.length, pages, has_next: page < pages },
    mock: false,
  }
}

test('admin authenticates, loads, paginates, filters and clears the session', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  const jobs = Array.from({ length: 13 }, (_, index) => makeJob(index))
  const firstLoad = deferred<void>()
  const requests: URL[] = []
  let authenticatedCalls = 0

  await page.route('**/api/v1/admin/jobs?*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    expect(request.method()).toBe('GET')
    expect(url.href).not.toContain(KEY)
    if (request.headers()['x-admin-key'] !== KEY) {
      await route.fulfill({
        status: 403,
        json: { error: { code: 'ADMIN_ACCESS_DENIED', message: 'Không có quyền.', details: [] } },
      })
      return
    }
    requests.push(url)
    authenticatedCalls++
    if (authenticatedCalls === 1) await firstLoad.promise
    await route.fulfill({ json: listBody(url, jobs) })
  })

  await page.goto('/#admin-status')
  const cards = page.getByRole('article')
  await page.getByLabel('Khóa quản trị').fill('wrong-test-key')
  await page.getByRole('button', { name: 'Kết nối', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Khóa quản trị thiếu hoặc không đúng.')
  await expect(cards).toHaveCount(0)

  await page.getByLabel('Khóa quản trị').fill(KEY)
  await page.getByRole('button', { name: 'Kết nối', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Đang tải trạng thái job')
  await expect(page.getByLabel('Khóa quản trị')).toHaveValue('')
  firstLoad.resolve()
  await expect(cards).toHaveCount(12)

  const failed = page.getByRole('article', { name: `Job ${jobs[0].job_id}`, exact: true })
  await expect(failed.locator('.admin-job-card__status')).toHaveText('Thất bại')
  await expect(failed.getByRole('progressbar')).toHaveAttribute('value', '100')
  await expect(failed).toContainText('BATCH_PARTIAL_FAILURE')
  await page.getByRole('button', { name: 'Trang sau' }).click()
  await expect(cards).toHaveCount(1)
  await expect(cards.first()).toContainText(jobs[12].job_id)
  await expect(cards.first()).toContainText('Chưa xác định tiến độ.')
  await expect(cards.first().getByRole('progressbar')).toHaveCount(0)

  await page.getByLabel('Loại job').selectOption('ingestion')
  await expect(cards).toHaveCount(12)
  await expect(page.getByRole('navigation', { name: 'Phân trang jobs' })).toContainText('Trang 1')
  await page.getByLabel('Trạng thái', { exact: true }).selectOption('failed')
  await expect(cards).toHaveCount(1)
  await expect(cards.first()).toContainText(jobs[0].job_id)
  const beforeReload = requests.length
  await page.getByRole('button', { name: 'Tải lại', exact: true }).click()
  await expect.poll(() => requests.length).toBe(beforeReload + 1)
  expect(requests[requests.length - 1].searchParams.get('kind')).toBe('ingestion')
  expect(requests[requests.length - 1].searchParams.get('status')).toBe('failed')
  await expect(cards).toHaveCount(1)

  await page.getByLabel('Loại job').selectOption('indexing')
  await expect(page.getByText('Không có job khớp bộ lọc.')).toBeVisible()
  await expect(cards).toHaveCount(0)
  await page.getByRole('button', { name: 'Chế độ tối' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

  await page.getByRole('button', { name: 'Xóa khóa khỏi phiên' }).click()
  await expect(page.getByText('Nhập khóa quản trị để tải trạng thái job.')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Phân trang jobs' })).toHaveCount(0)
  const stored = await page.evaluate(() => ({
    local: Object.values(localStorage),
    session: Object.values(sessionStorage),
  }))
  expect(JSON.stringify(stored)).not.toContain(KEY)
  const beforeRefresh = requests.length
  await page.reload()
  await expect(page.getByText('Nhập khóa quản trị để tải trạng thái job.')).toBeVisible()
  expect(requests).toHaveLength(beforeRefresh)
})

test('admin distinguishes HTTP configuration, network and contract errors and retries GET', async ({ page }) => {
  let scenario = 'unconfigured'
  let calls = 0
  await page.route('**/api/v1/admin/jobs?*', async route => {
    calls++
    expect(route.request().method()).toBe('GET')
    if (scenario === 'unconfigured') {
      await route.fulfill({
        status: 503,
        json: { error: { code: 'ADMIN_API_UNAVAILABLE', message: 'Chưa cấu hình.', details: [] } },
      })
    } else if (scenario === 'network') {
      await route.abort('failed')
    } else if (scenario === 'malformed') {
      await route.fulfill({ json: { mock: false, items: [] } })
    } else {
      await route.fulfill({ json: listBody(new URL(route.request().url()), []) })
    }
  })

  await page.goto('/#admin-status')
  await page.getByLabel('Khóa quản trị').fill(KEY)
  await page.getByRole('button', { name: 'Kết nối', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Backend chưa cấu hình API quản trị.')
  scenario = 'network'
  await page.getByRole('button', { name: 'Thử lại' }).click()
  await expect(page.getByRole('alert')).toContainText('Không thể kết nối API.')
  scenario = 'malformed'
  await page.getByRole('button', { name: 'Thử lại' }).click()
  await expect(page.getByRole('alert')).toContainText('Dữ liệu trạng thái job không đúng định dạng.')
  await expect(page.getByRole('article')).toHaveCount(0)
  scenario = 'empty'
  await page.getByRole('button', { name: 'Thử lại' }).click()
  await expect(page.getByText('Chưa có job nào để hiển thị.')).toBeVisible()
  expect(calls).toBe(4)
})

test('admin fixtures are available only on the development preview route', async ({ page }, testInfo) => {
  await page.goto('/#admin-status-preview')
  if (testInfo.project.name === 'production-mobile') {
    await expect(page.getByRole('heading', { name: 'Trạng thái job' })).toHaveCount(0)
    await expect(page.getByText('job-ingestion-001', { exact: true })).toHaveCount(0)
    await expect(page.locator('#search-panel')).toBeVisible()
  } else {
    await expect(page.getByText('Đây là chế độ preview riêng.', { exact: false })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'job-ingestion-001' })).toBeVisible()
    await expect(page.getByLabel('Khóa quản trị')).toHaveCount(0)
  }
})
