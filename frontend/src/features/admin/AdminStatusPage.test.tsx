import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AdminStatusPage } from './AdminStatusPage'

describe('AdminStatusPage', () => {
  it('hiển thị các trạng thái job trong fixture', () => {
    render(<AdminStatusPage />)

    expect(screen.getByText('Đang chờ')).toBeInTheDocument()
    expect(screen.getByText('Đang chạy')).toBeInTheDocument()
    expect(screen.getByText('Thành công')).toBeInTheDocument()
    expect(screen.getByText('Thất bại')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveValue(62)
    expect(screen.getByText('Không thể kết nối tới vector store')).toBeInTheDocument()
  })

  it('cho phép review trạng thái danh sách rỗng', async () => {
    const user = userEvent.setup()
    render(<AdminStatusPage />)

    await user.click(screen.getByRole('button', { name: 'Xem trạng thái danh sách rỗng' }))

    expect(screen.getByRole('status')).toHaveTextContent(
      'Chưa có job nào để hiển thị.',
    )
    expect(screen.getByRole('button', { name: 'Xem các job mẫu' })).toBeInTheDocument()
  })

  it('có thể quay lại danh sách job mẫu', async () => {
    const user = userEvent.setup()
    render(<AdminStatusPage />)

    await user.click(screen.getByRole('button', { name: 'Xem trạng thái danh sách rỗng' }))
    await user.click(screen.getByRole('button', { name: 'Xem các job mẫu' }))

    expect(screen.getByText('job-ingestion-001')).toBeInTheDocument()
    expect(screen.getByText('Đang chạy')).toBeInTheDocument()
  })
})