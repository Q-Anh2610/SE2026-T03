import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { JobStatusCard } from './JobStatusCard'
import type { JobMetadata } from './types'

const baseJob: JobMetadata = {
  job_id: 'a0b674d2-1286-401f-b73b-72cae159fcad',
  kind: 'indexing',
  runner: 'prepare_text_search_index',
  status: 'running',
  created_at: '2026-11-14T08:00:00Z',
  updated_at: '2026-11-14T08:00:01Z',
  started_at: '2026-11-14T08:00:01Z',
  finished_at: null,
  progress: {
    unit: 'assets',
    processed: null,
    total: null,
    percent: null,
  },
  result: null,
  error: null,
}

describe('JobStatusCard', () => {
  it('hiển thị tiến độ chưa xác định khi đang chạy', () => {
    render(<JobStatusCard job={baseJob} />)

    expect(screen.getByText('Đang chạy')).toBeInTheDocument()
    expect(screen.getByText('Chưa xác định tiến độ.')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('indexing thành công vẫn giữ progress null', () => {
    render(<JobStatusCard job={{
      ...baseJob,
      status: 'succeeded',
      finished_at: '2026-11-14T08:01:00Z',
      result: {
        persistence: null,
        input_count: null,
        succeeded: null,
        failed: null,
        skipped: null,
        manifest_sha256: null,
        exit_code: 0,
      },
    }} />)

    expect(screen.getByText('Thành công')).toBeInTheDocument()
    expect(screen.getByText('Chưa xác định tiến độ.')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByText('Mã thoát runner: 0')).toBeInTheDocument()
  })

  it('giữ trạng thái thất bại dù đã xử lý 100% input', () => {
    render(<JobStatusCard job={{
      ...baseJob,
      kind: 'ingestion',
      runner: 'ingestion.run_batch',
      status: 'failed',
      finished_at: '2026-11-14T08:01:00Z',
      progress: {
        unit: 'assets',
        processed: 1,
        total: 1,
        percent: 100,
      },
      error: {
        code: 'BATCH_PARTIAL_FAILURE',
        message: 'Có asset xử lý thất bại.',
      },
    }} />)

    expect(screen.getByText('Thất bại')).toBeInTheDocument()
    expect(screen.queryByText('Thành công')).not.toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveValue(100)
    expect(screen.getByText(
      'BATCH_PARTIAL_FAILURE: Có asset xử lý thất bại.',
    )).toBeInTheDocument()
  })
  it.each([
    ['postgresql', 'PostgreSQL'],
    ['local_files_only', 'Chỉ file local'],
    [null, 'Chưa xác định'],
  ] as const)(
    'hiển thị kết quả ingestion với persistence=%s',
    (persistence, label) => {
      render(<JobStatusCard job={{
        ...baseJob,
        kind: 'ingestion',
        runner: 'ingestion.run_batch',
        status: 'succeeded',
        finished_at: '2026-11-14T08:01:00Z',
        progress: {
          unit: 'assets',
          processed: 1,
          total: 1,
          percent: 100,
        },
        result: {
          persistence,
          input_count: 1,
          succeeded: 0,
          failed: 0,
          skipped: 1,
          manifest_sha256: 'a'.repeat(64),
          exit_code: null,
        },
      }} />)

      expect(screen.getByText(`Lưu trữ: ${label}`)).toBeInTheDocument()

      expect(
        screen.getByText('Đầu vào').nextElementSibling,
      ).toHaveTextContent('1')
      expect(
        screen.getByText('Tải thành công').nextElementSibling,
      ).toHaveTextContent('0')
      expect(
        screen.getByText('Thất bại', { selector: 'dt' }).nextElementSibling,
      ).toHaveTextContent('0')
      expect(
        screen.getByText('Tái sử dụng cache').nextElementSibling,
      ).toHaveTextContent('1')

      expect(screen.getByText(
        'Kết quả ingestion chưa xác nhận asset đã sẵn sàng tìm kiếm.',
      )).toBeInTheDocument()
    },
  )

  it('hiển thị job đang chờ, chưa bắt đầu và chưa có tiến độ', () => {
    render(<JobStatusCard job={{
      ...baseJob,
      status: 'queued',
      started_at: null,
      finished_at: null,
    }} />)

    expect(screen.getByText('Đang chờ')).toBeInTheDocument()
    expect(
      screen.getByText('Bắt đầu').nextElementSibling,
    ).toHaveTextContent('Chưa có')
    expect(
      screen.getByText('Kết thúc').nextElementSibling,
    ).toHaveTextContent('Chưa có')
    expect(screen.getByText('Chưa xác định tiến độ.')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('không suy diễn mã thoát indexing khi chưa xác định', () => {
    render(<JobStatusCard job={{
      ...baseJob,
      status: 'failed',
      finished_at: '2026-11-14T08:01:00Z',
      result: {
        persistence: null,
        input_count: null,
        succeeded: null,
        failed: null,
        skipped: null,
        manifest_sha256: null,
        exit_code: null,
      },
      error: {
        code: 'RUNNER_FAILED',
        message: 'Runner bị gián đoạn.',
      },
    }} />)

    expect(screen.getByText('Thất bại')).toBeInTheDocument()
    expect(screen.getByText(
      'Mã thoát runner: Chưa xác định',
    )).toBeInTheDocument()
    expect(screen.getByText(
      'Kết quả indexing chưa xác nhận index đang phục vụ đã được đổi.',
    )).toBeInTheDocument()
  })
})