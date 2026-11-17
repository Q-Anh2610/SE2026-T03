// #118: headless browser -> frontend sản phẩm -> API thật; không intercept HTTP.
import { createRequire } from 'node:module'
import { writeFile } from 'node:fs/promises'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium, expect } = require('@playwright/test')
const { W5_UI_URL: ui, W5_API_URL: api, W5_ADMIN_KEY: key, W5_IMAGE_QUERY: image, W5_BROWSER_REPORT: output } = process.env
if (!ui || !api || !key || !output) throw new Error('Run via verify_w5_api.py with an isolated test DB.')
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome', headless: true })
const report = { status: 'running', mocked_http: false, checks: [], search_events: [], feedbacks: [] }
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await context.newPage()
page.setDefaultTimeout(30000)
const tracker = page.getByRole('region', { name: 'Theo dõi job đã chọn' })

async function publicSearch(kind) {
  const tab = await context.newPage()
  try {
    await tab.goto(ui + (kind === 'image' ? '/#image-search' : '/'), { waitUntil: 'domcontentloaded' })
    const responsePromise = tab.waitForResponse(r => r.url().endsWith(`/api/v1/search/${kind}`) && r.request().method() === 'POST')
    if (kind === 'text') {
      const query = tab.getByRole('searchbox', { name: 'Bạn đang tìm asset nào?' })
      await query.fill('wooden chair')
      await query.press('Enter')
    } else {
      await tab.getByLabel(/Chọn hoặc thay ảnh/).setInputFiles(image)
      await tab.getByRole('button', { name: 'Tìm bằng ảnh', exact: true }).click()
    }
    const response = await responsePromise
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body.mock).toBe(false)
    expect(body.results.length).toBeGreaterThan(0)
    const source = kind === 'text' ? 'clip_text_to_preview' : 'clip_image_to_preview'
    expect(body.results[0].score_type).toBe('cosine')
    expect(body.results[0].retrieval_sources).toEqual([source])
    const card = tab.locator('.asset-grid > li').first()
    await expect(card).toBeVisible()
    await card.getByText('Chi tiết', { exact: true }).click()
    await expect(card.getByText(body.results[0].explanation, { exact: true })).toBeVisible()
    const ratingPromise = tab.waitForResponse(r => r.url().endsWith('/api/v1/feedback') && r.request().method() === 'POST')
    await card.getByRole('button', { name: 'Phù hợp', exact: true }).click()
    const saved = await ratingPromise
    expect(saved.status()).toBe(201)
    const feedback = await saved.json()
    expect(feedback.storage).toBe('postgresql')
    expect(feedback.search_event_id).toBe(body.search_event_id)
    await expect(card.getByRole('status')).toHaveText('Đã lưu đánh giá.')
    report.search_events.push({ kind, event_id: body.search_event_id, versions: body.versions })
    report.feedbacks.push(feedback)
  } finally {
    await tab.close()
  }
}

async function connect(path) {
  await page.goto(ui + path, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Khóa quản trị').fill('wrong-test-key')
  await page.getByRole('button', { name: 'Kết nối', exact: true }).click()
  await expect(page.locator('.admin-status-page__error')).toContainText('Khóa quản trị thiếu hoặc không đúng.')
  await page.getByLabel('Khóa quản trị').fill(key)
  await page.getByRole('button', { name: 'Kết nối', exact: true }).click()
}

try {
  if (process.env.W5_FAILED_JOB_ID) {
    await connect('/#admin-status/job/' + process.env.W5_FAILED_JOB_ID)
    await expect(tracker.getByText('Job đã kết thúc với lỗi. Không tự chạy lại.')).toBeVisible()
    await expect(tracker.getByText(/INDEXING_FAILED:/)).toBeVisible()
    report.checks.push('real_failed_job_rendered')
  } else {
    await publicSearch('text')
    await publicSearch('image')
    report.checks.push('text_image_explanation_feedback_before_reindex')
    await connect('/#admin-status')
    await expect(page.getByRole('button', { name: 'Yêu cầu reindex', exact: true })).toBeEnabled()
    let posts = 0
    page.on('request', r => { if (r.url().endsWith('/api/v1/admin/reindex') && r.method() === 'POST') posts++ })
    await page.getByRole('button', { name: 'Yêu cầu reindex', exact: true }).click()
    await page.getByRole('button', { name: 'Hủy yêu cầu', exact: true }).click()
    expect(posts).toBe(0)
    await page.getByRole('button', { name: 'Yêu cầu reindex', exact: true }).click()
    const acceptedPromise = page.waitForResponse(r => r.url().endsWith('/api/v1/admin/reindex') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Xác nhận reindex', exact: true }).click()
    const accepted = await acceptedPromise
    expect(accepted.status()).toBe(202)
    const job = await accepted.json()
    const payload = accepted.request().postDataJSON()
    const replay = await context.request.post(api + '/api/v1/admin/reindex', { headers: { 'X-Admin-Key': key }, data: payload })
    expect(replay.status()).toBe(200)
    expect((await replay.json()).job_id).toBe(job.job_id)
    const busy = await context.request.post(api + '/api/v1/admin/reindex', { headers: { 'X-Admin-Key': key }, data: { request_id: crypto.randomUUID() } })
    expect(busy.status()).toBe(409)
    report.job_id = job.job_id
    report.request_id = payload.request_id
    await page.getByRole('link', { name: 'Theo dõi job này' }).click()
    const state = await context.request.get(api + job.status_url, { headers: { 'X-Admin-Key': key } })
    const current = (await state.json()).job
    expect(['queued', 'running']).toContain(current.status)
    await expect(tracker.getByText('Chưa xác định tiến độ.')).toBeVisible()
    await publicSearch('text')
    report.checks.push('cancel_no_post_replay_conflict_and_search_feedback_during_reindex')
    await expect(tracker.getByText('Job đã hoàn thành. Index đang phục vụ chưa được chuyển.')).toBeVisible({ timeout: 300000 })
    await expect(tracker.getByText('reindex-clip-' + job.job_id.replaceAll('-', ''), { exact: true })).toBeVisible()
    await expect(tracker.getByText('Đã kiểm chứng', { exact: true })).toBeVisible()
    await publicSearch('text')
    await publicSearch('image')
    report.checks.push('terminal_success_and_public_search_feedback_after_reindex')
    expect(posts).toBe(1)
  }
  await page.getByRole('button', { name: 'Xóa khóa khỏi phiên' }).click()
  const stored = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))
  expect(stored).not.toContain(key)
  await page.reload()
  await expect(page.getByLabel('Khóa quản trị')).toHaveValue('')
  report.checks.push('admin_key_cleared_not_persisted')
  report.status = 'passed'
} catch (error) {
  report.status = 'failed'
  report.error_type = error?.name || 'Error'
  // Error text của Playwright có thể chứa locator/input; giữ ngoài report chia sẻ.
  process.stderr.write(String(error).replaceAll(key, '[redacted]') + '\n')
  process.exitCode = 1
} finally {
  await context.close()
  await browser.close()
  await writeFile(output, JSON.stringify(report, null, 2) + '\n')
}
