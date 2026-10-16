import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMockSearchClient } from './mock'
import { makeRequest } from '../../test/fixtures'

describe('development search mock', () => {
  beforeEach(() => { vi.useFakeTimers() })

  it.each([
    ['  GHẾ GỖ  ', ['mock-chair-01']],
    ['den ban', ['mock-lamp-01']],
    ['chair', ['mock-chair-01', 'mock-chair-02']],
    ['wood', ['mock-chair-01', 'mock-table-01', 'mock-box-01']],
    ['nonexistent asset', []],
  ])('matches metadata for %s', async (query, expectedIds) => {
    const pending = createMockSearchClient('success').search(makeRequest(query), new AbortController().signal)
    await vi.advanceTimersByTimeAsync(450)
    const response = await pending
    expect(response.query).toBe(query.trim())
    expect(response.results.map((result) => result.asset.asset_id)).toEqual(expectedIds)
    expect(response.results.map((result) => result.rank)).toEqual(expectedIds.map((_, position) => position + 1))
    expect(response.results.every((result) => result.score === null && result.asset.license === null)).toBe(true)
    expect(response.versions.model_version).toBe('mock-no-encoder')
  })

  it('respects limit, keeps assets unique and gives each search distinct IDs', async () => {
    const client = createMockSearchClient('success')
    const first = client.search(makeRequest('wood', 2), new AbortController().signal)
    const second = client.search(makeRequest('wood', 2), new AbortController().signal)
    await vi.advanceTimersByTimeAsync(450)
    const [firstResponse, secondResponse] = await Promise.all([first, second])
    expect(firstResponse.results).toHaveLength(2)
    expect(new Set(firstResponse.results.map((result) => result.asset.asset_id)).size).toBe(2)
    expect(firstResponse.query_id).not.toBe(secondResponse.query_id)
    expect(firstResponse.search_event_id).not.toBe(secondResponse.search_event_id)
  })

  it('does not resolve before the configured development delay', async () => {
    const settled = vi.fn()
    const pending = createMockSearchClient('success').search(makeRequest(), new AbortController().signal).then(settled)
    await vi.advanceTimersByTimeAsync(449)
    expect(settled).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    await pending
    expect(settled).toHaveBeenCalledOnce()
  })

  it('forces the empty scenario even for a matching query', async () => {
    const pending = createMockSearchClient('empty').search(makeRequest(), new AbortController().signal)
    await vi.advanceTimersByTimeAsync(450)
    expect((await pending).results).toEqual([])
  })

  it('rejects the error scenario without returning fake successful results', async () => {
    const pending = createMockSearchClient('error').search(makeRequest(), new AbortController().signal)
    const assertion = expect(pending).rejects.toThrow('Lỗi kết nối minh họa')
    await vi.advanceTimersByTimeAsync(450)
    await assertion
  })

  it('rejects an invalid request before scheduling work', async () => {
    await expect(createMockSearchClient('success').search(makeRequest(' '), new AbortController().signal)).rejects.toThrow()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('rejects a signal aborted before search starts', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(createMockSearchClient('success').search(makeRequest(), controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
    expect(vi.getTimerCount()).toBe(0)
  })

  it('cancels pending work and removes the timer on abort', async () => {
    const controller = new AbortController()
    const pending = createMockSearchClient('success').search(makeRequest(), controller.signal)
    const assertion = expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    controller.abort()
    await assertion
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not leak changes to result metadata between requests', async () => {
    const client = createMockSearchClient('success')
    const pending = client.search(makeRequest(), new AbortController().signal)
    await vi.advanceTimersByTimeAsync(450)
    const response = await pending
    response.results[0]!.asset.tags.push('changed')
    response.results[0]!.asset.formats.push('changed')
    response.results[0]!.asset.name = 'changed'
    const next = client.search(makeRequest(), new AbortController().signal)
    await vi.advanceTimersByTimeAsync(450)
    const nextResponse = await next
    expect(nextResponse.results[0]!.asset.name).toBe('Ghế gỗ đơn giản')
    expect(nextResponse.results[0]!.asset.tags).not.toContain('changed')
    expect(nextResponse.results[0]!.asset.formats).toEqual(['glb'])
  })
})
