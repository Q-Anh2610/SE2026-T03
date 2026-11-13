import { afterEach, expect, it, vi } from 'vitest'
import { MAX_NOTIFICATION_BODY_LENGTH, MAX_NOTIFICATION_TITLE_LENGTH, notifyBusinessEvent } from './business-notification'

const construct = vi.fn()

class FakeNotification {
  static permission: NotificationPermission = 'granted'
  constructor(title: string, options?: NotificationOptions) {
    construct(title, options)
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  construct.mockReset()
  FakeNotification.permission = 'granted'
})

it('accepts a title exactly at the 120-character boundary', () => {
  vi.stubGlobal('Notification', FakeNotification)

  expect(notifyBusinessEvent('x'.repeat(MAX_NOTIFICATION_TITLE_LENGTH), 'saved')).toBe(true)
  expect(construct).toHaveBeenCalledOnce()
})

it('rejects a title over the 120-character boundary', () => {
  vi.stubGlobal('Notification', FakeNotification)

  expect(notifyBusinessEvent('x'.repeat(MAX_NOTIFICATION_TITLE_LENGTH + 1), 'saved')).toBe(false)
  expect(construct).not.toHaveBeenCalled()
})

it('truncates an oversized body to the configured cap', () => {
  vi.stubGlobal('Notification', FakeNotification)

  expect(notifyBusinessEvent('Saved', 'x'.repeat(MAX_NOTIFICATION_BODY_LENGTH + 30))).toBe(true)
  expect(construct.mock.calls[0][1].body).toHaveLength(MAX_NOTIFICATION_BODY_LENGTH)
})

it.each(['default', 'denied'] as const)('skips notification when permission is %s without prompting', (permission) => {
  FakeNotification.permission = permission
  vi.stubGlobal('Notification', FakeNotification)

  expect(notifyBusinessEvent('Saved', 'done')).toBe(false)
  expect(construct).not.toHaveBeenCalled()
})

it('skips safely when the browser has no Notification API', () => {
  vi.stubGlobal('Notification', undefined)

  expect(notifyBusinessEvent('Saved', 'done')).toBe(false)
})

it('contains constructor failure and reports no notification delivery', () => {
  construct.mockImplementation(() => { throw new Error('browser notification failed') })
  vi.stubGlobal('Notification', FakeNotification)

  expect(notifyBusinessEvent('Saved', 'done')).toBe(false)
})

const pairwiseCases = [
  ['granted', 'ok', 'under', 'under'],
  ['granted', 'throws', 'exact', 'under'],
  ['granted', 'ok', 'over', 'over'],
  ['denied', 'throws', 'under', 'over'],
  ['denied', 'ok', 'exact', 'over'],
  ['denied', 'throws', 'over', 'under'],
  ['default', 'ok', 'under', 'under'],
  ['default', 'throws', 'exact', 'under'],
  ['default', 'ok', 'over', 'over'],
  ['unsupported', 'throws', 'under', 'over'],
  ['unsupported', 'ok', 'exact', 'over'],
  ['unsupported', 'throws', 'over', 'under'],
] as const

it.each(pairwiseCases)('pairwise: permission=%s sender=%s title=%s body=%s', (permission, sender, titleSize, bodySize) => {
  const permissions: Record<string, NotificationPermission> = { granted: 'granted', denied: 'denied', default: 'default' }
  FakeNotification.permission = permissions[permission] ?? 'granted'
  construct.mockImplementation(() => {
    if (sender === 'throws') throw new Error('simulated browser failure')
  })
  if (permission === 'unsupported') vi.stubGlobal('Notification', undefined)
  else vi.stubGlobal('Notification', FakeNotification)
  const titles = { under: 'Title', exact: 'x'.repeat(MAX_NOTIFICATION_TITLE_LENGTH), over: 'x'.repeat(MAX_NOTIFICATION_TITLE_LENGTH + 1) }
  const bodies = { under: 'x'.repeat(10), over: 'x'.repeat(MAX_NOTIFICATION_BODY_LENGTH + 1) }
  const expected = permission === 'granted' && sender === 'ok' && titleSize !== 'over'

  expect(notifyBusinessEvent(titles[titleSize], bodies[bodySize])).toBe(expected)
  if (expected) expect(construct.mock.calls.at(-1)?.[1].body.length).toBeLessThanOrEqual(MAX_NOTIFICATION_BODY_LENGTH)
})

it('measures a synthetic burst of 100 notification tasks against the local p95 target', async () => {
  vi.stubGlobal('Notification', FakeNotification)
  const started = performance.now()
  const durations = await Promise.all(Array.from({ length: 100 }, async () => {
    const before = performance.now()
    notifyBusinessEvent('Saved', 'synthetic feedback event')
    return performance.now() - before
  }))
  const p95 = [...durations].sort((a, b) => a - b)[94]
  console.info(`notification-harness: concurrency=100 p95=${p95.toFixed(3)}ms wall=${(performance.now() - started).toFixed(3)}ms`)
  expect(p95).toBeLessThanOrEqual(3000)
})
