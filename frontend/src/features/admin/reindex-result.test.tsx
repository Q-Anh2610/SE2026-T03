import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { reindexJob } from '../../test/admin-reindex'
import { parseJobDetailResponse } from './contract'
import { JobStatusCard } from './JobStatusCard'

describe('reindex result compatibility', () => {
  it('giữ và hiển thị versions/count/index reference từ API', () => {
    const job = reindexJob('succeeded')
    expect(parseJobDetailResponse({ job, mock: false }).job).toEqual(job)
    render(<JobStatusCard job={job} />)
    for (const value of ['reindex-clip-fixture', 'clip@fixture-revision', 'home-interior-clear-200-v3@fixture-hash', 'reindex-fixture', 'b'.repeat(64), '200 / 200', '200 / 200 / 0 / 0', 'Đã kiểm chứng']) {
      expect(screen.getByText(value)).toBeInTheDocument()
    }
    expect(screen.getByText(/chưa xác nhận index đang phục vụ/)).toBeInTheDocument()
  })
  it.each([null, false] as const)('search_verified=%s không gắn đã kiểm chứng', search_verified => {
    const job = reindexJob('succeeded')
    job.result = { ...job.result!, search_verified }
    render(<JobStatusCard job={job} />)
    expect(screen.getByText(search_verified === false ? 'Chưa đạt' : 'Chưa có thông tin')).toBeInTheDocument()
  })
  it('chấp nhận tất cả trường mới null và job cũ thiếu trường mới', () => {
    const job = reindexJob('succeeded')
    const keys = ['index_version', 'model_version', 'dataset_snapshot', 'asset_count', 'point_count', 'index_ref', 'index_manifest_sha256', 'search_verified'] as const
    for (const key of keys) {
      const candidate = { ...job, result: { ...job.result, [key]: null } }
      expect(parseJobDetailResponse({ job: candidate, mock: false }).job).toEqual(candidate)
    }
    const legacy = { ...job.result! }
    for (const key of keys) delete legacy[key]
    expect(() => parseJobDetailResponse({ job: { ...job, result: legacy }, mock: false })).not.toThrow()
  })
  it.each([
    ['index_version', 1], ['model_version', {}], ['dataset_snapshot', []],
    ['index_ref', true], ['index_manifest_sha256', 3],
    ['asset_count', -1], ['point_count', 1.5], ['search_verified', 'true'],
  ])('từ chối result %s sai kiểu', (field, value) => {
    const job = reindexJob('succeeded')
    expect(() => parseJobDetailResponse({ job: { ...job, result: { ...job.result, [field]: value } }, mock: false })).toThrow()
  })
})
