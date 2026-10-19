import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMockSearchClient, createMockSearchResponse, mockAssets } from './mock'
import { makeRequest } from '../../test/fixtures'

describe('development search mock', () => {
  it('applies filters before pagination and starts each page at rank one', () => {
    const first = createMockSearchResponse('glb', 2, 'success', 1, { category: 'Nội thất', format: 'glb' })
    const second = createMockSearchResponse('glb', 2, 'success', 2, { category: 'Nội thất' })
    expect(first.pagination).toEqual({ page: 1, limit: 2, total: 3, pages: 2, has_next: true })
    expect(second.results.map(result => result.rank)).toEqual([1])
    expect(second.results[0].asset.asset_id).toBe('mock-table-01')
    expect(createMockSearchResponse('glb', 2, 'success', 3).results).toEqual([expect.objectContaining({ rank: 1 }), expect.objectContaining({ rank: 2 })])
    expect(createMockSearchResponse('glb', 2, 'success', 99).results).toEqual([])
    expect(createMockSearchResponse('glb', 12, 'success', 1, { format: 'obj' }).results).toEqual([])
    expect(createMockSearchResponse('glb', 12, 'success', 1, { license: 'CC0' }).results).toEqual([])
    expect(createMockSearchResponse('glb', 12, 'success', 1, { face_count_min: 0 }).results).toEqual([])
    expect(createMockSearchResponse('glb', 12, 'success', 1, { face_count_max: 10 }).results).toEqual([])
  })

  it('matches known numeric metadata inclusively and excludes unknown values', () => {
    const original = { ...mockAssets[0] }
    try {
      Object.assign(mockAssets[0], { face_count: 100, license: 'CC0' })
      for (const filters of [{ face_count_min: 100 }, { face_count_max: 100 }, { license: 'CC0' }, { category: null, format: null, face_count_min: null, face_count_max: null }]) {
        expect(createMockSearchResponse('glb', 12, 'success', 1, filters).results.some(result => result.asset.asset_id === original.asset_id)).toBe(true)
      }
      expect(createMockSearchResponse('glb', 12, 'success', 1, { face_count_min: 101 }).results).toEqual([])
      expect(createMockSearchResponse('glb', 12, 'success', 1, { face_count_max: 99 }).results).toEqual([])
    } finally { Object.assign(mockAssets[0], original) }
  })
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
