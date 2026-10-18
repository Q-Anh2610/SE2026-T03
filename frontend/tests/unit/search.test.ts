import { describe, expect, it } from 'vitest'
import { createMockSearchResponse, findMockAssets, normalizeQuery } from '../../src/features/search/mock'

describe('mock keyword search', () => {
  it.each(['ghe go', 'GHẾ GỖ', '  ghế   gỗ  ', 'ghe\u0302\u0301 go\u0302\u0303'])(
    'Vietnamese accent/case variant %s returns the same wooden chair', (query) => {
      expect(findMockAssets(query).map((asset) => asset.asset_id)).toEqual(['mock-chair-01'])
    },
  )
  it('matches English fixture keywords', () => {
    expect(findMockAssets('wood chair').map((asset) => asset.asset_id)).toEqual(['mock-chair-01'])
  })
  it('requires all query words', () => { expect(findMockAssets('ghế đèn')).toEqual([]) })
  it('matches file formats without case sensitivity', () => {
    expect(findMockAssets('glb').map((asset) => asset.asset_id)).toEqual(['mock-chair-01', 'mock-chair-02', 'mock-table-01', 'mock-lamp-01', 'mock-vase-01', 'mock-box-01'])
  })
  it.each(['', '   ', '\n\t'])('empty query %j browses all fixtures', (query) => {
    expect(findMockAssets(query)).toHaveLength(6)
  })
  it('unknown query returns an empty response', () => {
    expect(createMockSearchResponse('khong co mau').results).toEqual([])
  })
  it('treats HTML-looking input as ordinary text', () => {
    expect(findMockAssets('<script>alert(1)</script>')).toEqual([])
  })
  it('normalizes Vietnamese đ', () => { expect(normalizeQuery('ĐÈN')).toBe('den') })
  it('does not mutate fixtures between different queries', () => {
    const original = findMockAssets('')
    findMockAssets('lamp')
    expect(findMockAssets('')).toEqual(original)
  })
})

describe('draft response fixture', () => {
  it('preserves unique assets and consecutive ranks', () => {
    const { results } = createMockSearchResponse('gỗ')
    expect(new Set(results.map(({ asset }) => asset.asset_id)).size).toBe(3)
    expect(results.map(({ rank }) => rank)).toEqual([1, 2, 3])
  })
  it('starts filtered response ranks at one', () => {
    expect(createMockSearchResponse('lamp').results[0].rank).toBe(1)
  })
  it('preserves honest provenance and excludes illustration fields', () => {
    for (const { asset, retrieval_sources } of createMockSearchResponse('gỗ').results) {
      expect(asset.source).toBe('fixture')
      for (const key of ['license', 'author', 'source_url', 'thumbnail_url', 'face_count'] as const) {
        expect(asset[key]).toBeNull()
      }
      for (const key of ['illustration', 'color', 'keywords']) expect(asset).not.toHaveProperty(key)
      expect(retrieval_sources).toEqual(['mock_metadata'])
    }
  })
  it('identifies mock versions and trims query', () => {
    expect(createMockSearchResponse(' ghế ')).toMatchObject({
      query: 'ghế', versions: { model_version: 'mock-no-encoder',
      index_version: 'mock-w1', config_version: 'mock-text-v1' },
    })
  })
})
