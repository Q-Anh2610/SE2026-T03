import { describe, expect, it } from 'vitest'
import { parseResponse } from './contract'
import { makeLiveResponse, makeRequest, makeResponse } from '../../test/fixtures'

describe('live text search W3 response invariants (#63)', () => {
  it('preserves mock:false, dataset snapshot and IDs from the API', () => {
    const response = makeLiveResponse()
    expect(parseResponse(response, makeRequest())).toBe(response)
    expect(response.mock).toBe(false)
    expect(response.query_id).toBe(response.search_event_id)
  })

  it.each([undefined, null, 'false', 0])('rejects a missing or non-boolean mock flag %s', (mock) => {
    expect(() => parseResponse({ ...makeLiveResponse(), mock }, makeRequest())).toThrow('không đúng contract')
  })

  it.each(['model_version', 'index_version', 'config_version', 'dataset_snapshot'])('requires real, nonempty %s', (key) => {
    for (const value of [undefined, null, 1, '', '   ', 'mock-v1', ' MOCK-v1 ']) {
      const response = makeLiveResponse()
      Reflect.set(response.versions, key, value)
      expect(() => parseResponse(response, makeRequest())).toThrow('không đúng contract')
    }
  })

  it('rejects mismatched event IDs', () => {
    const response = { ...makeLiveResponse(), query_id: 'different-query-id' }
    expect(() => parseResponse(response, makeRequest())).toThrow('không đúng contract')
  })

  it.each([0, 200])('accepts a bounded candidate total %s and an out-of-range empty page', (total) => {
    const response = makeLiveResponse()
    response.results = []
    response.pagination = { page: 101, limit: 2, total, pages: Math.ceil(total / 2), has_next: false }
    expect(parseResponse(response, { ...makeRequest(undefined, 2), page: 101 })).toBe(response)
  })

  it('rejects total above 200 even when pagination and result count are consistent', () => {
    const response = makeLiveResponse()
    response.results = []
    response.pagination = { page: 102, limit: 2, total: 201, pages: 101, has_next: false }
    expect(() => parseResponse(response, { ...makeRequest(undefined, 2), page: 102 })).toThrow('không đúng contract')
  })

  it('keeps page-relative ranks at one on later live pages', () => {
    const response = makeLiveResponse()
    response.pagination = { page: 2, limit: 2, total: 3, pages: 2, has_next: false }
    const request = { ...makeRequest(undefined, 2), page: 2 }
    expect(parseResponse(response, request).results[0].rank).toBe(1)
    response.results[0].rank = 3
    expect(() => parseResponse(response, request)).toThrow('không đúng contract')
  })

  it('keeps explicitly marked legacy mock responses separate without fabricating snapshot or equal IDs', () => {
    const response = makeResponse()
    expect(parseResponse(response, makeRequest())).toBe(response)
    expect(response.mock).toBe(true)
    expect(response.versions).not.toHaveProperty('dataset_snapshot')
    expect(response.query_id).not.toBe(response.search_event_id)
  })
})
