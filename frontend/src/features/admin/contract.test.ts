import { describe, expect, it } from 'vitest'
import {
  parseJobDetailResponse,
  parseJobListResponse,
} from './contract'
import type { JobMetadata, JobStatus } from './types'

function makeResult() {
  return {
    persistence: 'postgresql' as const,
    input_count: 1,
    succeeded: 1,
    failed: 0,
    skipped: 0,
    manifest_sha256: 'a'.repeat(64),
    exit_code: null,
  }
}

function makeJob(status: JobStatus = 'succeeded'): JobMetadata {
  const finished = status === 'succeeded' || status === 'failed'

  return {
    job_id: 'a0b674d2-1286-401f-b73b-72cae159fcad',
    kind: 'ingestion',
    runner: 'ingestion.run_batch',
    status,
    created_at: '2026-11-14T08:00:00Z',
    updated_at: '2026-11-14T08:01:00Z',
    started_at: status === 'queued' ? null : '2026-11-14T08:00:01Z',
    finished_at: finished ? '2026-11-14T08:01:00Z' : null,
    progress: {
      unit: 'assets',
      processed: finished ? 1 : null,
      total: finished ? 1 : null,
      percent: finished ? 100 : null,
    },
    result: finished ? makeResult() : null,
    error: status === 'failed'
      ? { code: 'RUNNER_FAILED', message: 'Runner thất bại.' }
      : null,
  }
}

function listBody(items: JobMetadata[] = [makeJob()]) {
  return {
    items,
    pagination: {
      page: 1,
      limit: 12,
      total: items.length,
      pages: items.length === 0 ? 0 : 1,
      has_next: false,
    },
    mock: false,
  }
}

function expectInvalidDetail(job: unknown) {
  expect(() => parseJobDetailResponse({
    job,
    mock: false,
  })).toThrow('Dữ liệu trạng thái job không đúng định dạng.')
}

describe('jobs response contract', () => {
  it.each(['queued', 'running', 'succeeded', 'failed'] as const)(
    'chấp nhận trạng thái %s và giữ nguyên dữ liệu',
    (status) => {
      const job = makeJob(status)

      expect(parseJobDetailResponse({ job, mock: false })).toEqual({
        job,
        mock: false,
      })
    },
  )

  it('chấp nhận indexing thành công với progress và số đếm null', () => {
    const job: JobMetadata = {
      ...makeJob(),
      kind: 'indexing',
      runner: 'prepare_text_search_index',
      progress: {
        unit: 'assets',
        processed: null,
        total: null,
        percent: null,
      },
      result: {
        persistence: null,
        input_count: null,
        succeeded: null,
        failed: null,
        skipped: null,
        manifest_sha256: null,
        exit_code: 0,
      },
    }

    expect(parseJobDetailResponse({ job, mock: false }).job).toEqual(job)
  })

  it('chấp nhận ingestion chỉ lưu file local', () => {
    const job = {
      ...makeJob(),
      result: { ...makeResult(), persistence: 'local_files_only' },
    }

    expect(parseJobDetailResponse({ job, mock: false }).job).toEqual(job)
  })

  it('chấp nhận danh sách có dữ liệu và danh sách rỗng', () => {
    for (const body of [listBody(), listBody([])]) {
      expect(parseJobListResponse(body)).toEqual(body)
    }
  })

  it('chấp nhận trang vượt phạm vi với total thật', () => {
    const body = {
      items: [],
      pagination: {
        page: 2,
        limit: 12,
        total: 1,
        pages: 1,
        has_next: false,
      },
      mock: false,
    }

    expect(parseJobListResponse(body)).toEqual(body)
  })

  it.each([
    null,
    [],
    {},
    { ...listBody(), mock: true },
    { ...listBody(), items: null },
    { ...listBody(), items: [null] },
    { ...listBody(), pagination: null },
  ])('từ chối envelope danh sách sai: %j', (body) => {
    expect(() => parseJobListResponse(body)).toThrow()
  })

  it.each([
    null,
    [],
    {},
    { job: makeJob(), mock: true },
    { job: null, mock: false },
  ])('từ chối envelope chi tiết sai: %j', (body) => {
    expect(() => parseJobDetailResponse(body)).toThrow()
  })

  it.each<[string, unknown]>([
    ['job_id', 123],
    ['job_id', 'not-a-uuid'],
    ['kind', 'unknown'],
    ['status', 'unknown'],
    ['runner', null],
    ['created_at', 123],
    ['created_at', 'not-a-date'],
    ['created_at', '2026-11-14T08:00:00'],
    ['created_at', '2026-99-99T08:00:00Z'],
    ['updated_at', null],
    ['started_at', 'invalid'],
    ['finished_at', 'invalid'],
    ['progress', null],
    ['result', []],
    ['error', []],
    ['error', { code: 123, message: 'Lỗi' }],
    ['error', { code: 'RUNNER_FAILED', message: null }],
  ])('từ chối trường job sai: %s = %j', (field, value) => {
    expectInvalidDetail({ ...makeJob(), [field]: value })
  })

  it.each<[string, unknown]>([
    ['unit', 'percent'],
    ['processed', -1],
    ['processed', 0.5],
    ['total', '1'],
    ['percent', '100'],
    ['percent', Infinity],
    ['percent', -1],
    ['percent', 101],
  ])('từ chối progress sai: %s = %j', (field, value) => {
    expectInvalidDetail({
      ...makeJob(),
      progress: { ...makeJob().progress, [field]: value },
    })
  })

  it.each<[string, unknown]>([
    ['persistence', 'unknown'],
    ['input_count', -1],
    ['succeeded', '1'],
    ['failed', 0.5],
    ['skipped', undefined],
    ['manifest_sha256', 123],
    ['exit_code', '0'],
    ['exit_code', 0.5],
  ])('từ chối result sai: %s = %j', (field, value) => {
    expectInvalidDetail({
      ...makeJob(),
      result: { ...makeResult(), [field]: value },
    })
  })

  it.each<[string, unknown]>([
    ['page', '1'],
    ['page', 0],
    ['limit', '12'],
    ['limit', 0],
    ['limit', 51],
    ['total', -1],
    ['pages', -1],
    ['pages', 2],
    ['has_next', 'false'],
    ['has_next', true],
  ])('từ chối pagination sai: %s = %j', (field, value) => {
    const body = listBody()

    expect(() => parseJobListResponse({
      ...body,
      pagination: { ...body.pagination, [field]: value },
    })).toThrow()
  })

  it('từ chối số items không khớp pagination', () => {
    expect(() => parseJobListResponse({
      ...listBody(),
      items: [],
    })).toThrow()
  })

  it('từ chối job ID trùng trong cùng trang', () => {
    expect(() => parseJobListResponse(
      listBody([makeJob(), makeJob()]),
    )).toThrow()
  })
})