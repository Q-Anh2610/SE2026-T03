import { describe, expect, it } from 'vitest'
import { isHttpUrl, parseResponse, validateFilters, validateRequest } from './contract'
import { makeRequest, makeResponse } from '../../test/fixtures'
import type { SearchRequest, SearchResponse } from './types'

describe('search request contract', () => {
  it.each([null, 0, -1, 1.2, true, '2', Infinity, NaN])('rejects invalid page %s', page => {
    expect(() => validateRequest({ ...makeRequest(), page } as SearchRequest)).toThrow('Trang')
  })
  it('defaults omitted page to one and accepts supported nullable filters', () => {
    const request = { ...makeRequest(), page: undefined, filters: { category: 'Nội thất', format: 'glb', license: null, face_count_min: 0, face_count_max: 100 } }
    expect(validateRequest(request)).toMatchObject({ page: 1, filters: request.filters })
  })
  it.each([{ category: '' }, { category: 2 }, { license: false }, { format: [] }, { face_count_min: true }, { face_count_max: -1 }, { face_count_min: 1.5 }, { face_count_min: 10, face_count_max: 2 }])('rejects invalid filters %j', filters => {
    expect(() => validateFilters(filters as SearchRequest['filters'])).toThrow('Bộ lọc không hợp lệ')
  })
  it('normalizes whitespace without changing the original request', () => {
    const request = makeRequest('  ghế gỗ  ')
    expect(validateRequest(request)).toEqual(makeRequest())
    expect(request.query).toBe('  ghế gỗ  ')
  })

  it.each(['', '  \n ', 'a'.repeat(501)])('rejects an empty or oversized query', (query) => {
    expect(() => validateRequest(makeRequest(query))).toThrow('1 đến 500 ký tự')
  })

  it('counts Unicode code points instead of UTF-16 code units', () => {
    expect(validateRequest(makeRequest('😀'.repeat(500))).query).toHaveLength(1000)
    expect(() => validateRequest(makeRequest('😀'.repeat(501)))).toThrow()
  })

  it.each([0, 51, -1, 1.5, NaN, Infinity])('rejects invalid limit %s', (limit) => {
    expect(() => validateRequest(makeRequest('ghế', limit))).toThrow('số nguyên từ 1 đến 50')
  })

  it.each([1, 50])('accepts boundary limit %s', (limit) => {
    expect(validateRequest(makeRequest('ghế', limit)).limit).toBe(limit)
  })

  it.each([null, [], 'category', { unknown: 'Nội thất' }])('rejects unsupported or malformed filters', (filters) => {
    const request = { ...makeRequest(), filters } as unknown as SearchRequest
    expect(() => validateRequest(request)).toThrow('Bộ lọc không hợp lệ')
  })
})

describe('asset URLs', () => {
  it.each(['https://example.com/preview.png', 'http://localhost:8000/assets/1'])('accepts HTTP(S) %s', (url) => {
    expect(isHttpUrl(url)).toBe(true)
  })

  it.each([null, 1, '', '/preview.png', 'invalid', 'javascript:alert(1)', 'data:image/png;base64,AA',
    'https://user:password@example.com/image.png', 'https://user@example.com/image.png'])('rejects unsafe or invalid URLs', (url) => {
    expect(isHttpUrl(url)).toBe(false)
  })
})

describe('search response contract', () => {
  it.each([undefined, null, [], { page: 2 }, { page: 1, limit: 12, total: -1, pages: 0, has_next: false },
    { page: 1, limit: 12, total: 1.5, pages: 1, has_next: false },
    { page: 1, limit: 6, total: 1, pages: 1, has_next: false },
    { page: 1, limit: 12, total: 1, pages: 2, has_next: false },
    { page: 1, limit: 12, total: 1, pages: 1, has_next: true },
    { page: 1, limit: 12, total: 13, pages: 2, has_next: true }])('rejects inconsistent pagination %j', pagination => {
    expect(() => parseResponse({ ...makeResponse(), pagination }, makeRequest())).toThrow('không đúng contract')
  })
  it('accepts a second page with ranks restarting at one, and a page past the end', () => {
    const response = { ...makeResponse(), pagination: { page: 2, limit: 2, total: 3, pages: 2, has_next: false } }
    expect(parseResponse(response, { ...makeRequest('ghế gỗ', 2), page: 2 }).results[0].rank).toBe(1)
    expect(parseResponse({ ...response, results: [], pagination: { ...response.pagination, page: 99 } }, { ...makeRequest('ghế gỗ', 2), page: 99 }).results).toEqual([])
  })
  it('accepts results with unknown metadata explicitly set to null', () => {
    const response = makeResponse()
    expect(parseResponse(response, makeRequest())).toEqual(response)
  })

  it('accepts a successful empty result', () => {
    const response = { ...makeResponse(), results: [], pagination: { page: 1, limit: 12, total: 0, pages: 0, has_next: false } }
    expect(parseResponse(response, makeRequest()).results).toEqual([])
  })

  it('accepts populated metadata and finite scores without assigning percentage semantics', () => {
    const response = makeResponse()
    const result = response.results[0]!
    Object.assign(result.asset, {
      face_count: 0, author: 'Test author', license: 'Test license',
      thumbnail_url: 'https://example.com/image.png', source_url: 'https://example.com/asset',
    })
    result.score = -0.25
    expect(parseResponse(response, makeRequest()).results[0]?.score).toBe(-0.25)
  })

  it.each([null, [], 'not-json', 42])('rejects a non-object payload', (payload) => {
    expect(() => parseResponse(payload, makeRequest())).toThrow('không đúng contract')
  })

  it.each([
    ['query_id', undefined], ['query_id', ''], ['search_event_id', 1], ['search_event_id', ''],
    ['query', 'another query'], ['versions', null], ['results', null], ['results', {}],
  ])('rejects an invalid response field %s', (key, invalidValue) => {
    const response = { ...makeResponse(), [key]: invalidValue }
    expect(() => parseResponse(response, makeRequest())).toThrow('không đúng contract')
  })

  it.each(['model_version', 'index_version', 'config_version'])('requires version field %s', (key) => {
    const response = makeResponse()
    Reflect.deleteProperty(response.versions, key)
    expect(() => parseResponse(response, makeRequest())).toThrow()
  })

  it('rejects more results than the requested limit', () => {
    const response = makeResponse()
    response.results.push({ ...response.results[0]!, rank: 2, asset: { ...response.results[0]!.asset, asset_id: 'test-second' } })
    expect(() => parseResponse(response, makeRequest('ghế gỗ', 1))).toThrow()
  })

  it('rejects duplicate assets even when their ranks differ', () => {
    const response = makeResponse()
    response.results.push({ ...response.results[0]!, rank: 2 })
    response.pagination.total = 2
    expect(() => parseResponse(response, makeRequest())).toThrow()
  })

  it.each([null, 2, 'asset'])('rejects a non-object result', (result) => {
    expect(() => parseResponse({ ...makeResponse(), results: [result] }, makeRequest())).toThrow()
  })

  const invalidResultFields: [string, unknown][] = [
    ['rank', 0], ['rank', 2], ['rank', 1.5], ['asset', null],
    ['retrieval_sources', 'clip'], ['retrieval_sources', [1]], ['explanation', null],
    ['score', undefined], ['score', '0.95'], ['score', NaN], ['score', Infinity],
  ]
  it.each(invalidResultFields)('rejects an invalid result field %s', (key, value) => {
    const response = makeResponse()
    Reflect.set(response.results[0]!, key, value)
    expect(() => parseResponse(response, makeRequest())).toThrow()
  })

  const invalidAssetFields: [string, unknown][] = [
    ['asset_id', ''], ['name', ''], ['name', null], ['description', 1], ['category', 1], ['source', null],
    ['tags', null], ['tags', [1]], ['formats', undefined], ['formats', [1]],
    ['face_count', -1], ['face_count', 1.5], ['face_count', '1'], ['face_count', undefined],
    ['author', 42], ['license', undefined], ['source_url', 'javascript:alert(1)'],
    ['thumbnail_url', '/relative.png'], ['thumbnail_url', 'https://user:secret@example.com/image.png'],
  ]
  it.each(invalidAssetFields)('rejects invalid asset metadata %s', (key, value) => {
    const response: SearchResponse = makeResponse()
    Reflect.set(response.results[0]!.asset, key, value)
    expect(() => parseResponse(response, makeRequest())).toThrow()
  })
})

it('accepts missing description and category represented as null', () => {
  const response = makeResponse()
  response.results[0]!.asset.description = null
  response.results[0]!.asset.category = null
  expect(parseResponse(response, makeRequest())).toEqual(response)
})
