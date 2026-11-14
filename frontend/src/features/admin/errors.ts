export type AdminJobsErrorKind =
  | 'access_denied'
  | 'unconfigured'
  | 'invalid_request'
  | 'not_found'
  | 'network'
  | 'contract'
  | 'server'

const messages: Record<AdminJobsErrorKind, string> = {
  access_denied: 'Khóa quản trị thiếu hoặc không đúng.',
  unconfigured: 'Backend chưa cấu hình API quản trị.',
  invalid_request: 'Tham số tải trạng thái job không hợp lệ.',
  not_found: 'Không tìm thấy job.',
  network: 'Không thể kết nối API. Vui lòng thử lại.',
  contract: 'Dữ liệu trạng thái job không đúng định dạng.',
  server: 'Không thể tải trạng thái job. Vui lòng thử lại.',
}

export class AdminJobsError extends Error {
  readonly kind: AdminJobsErrorKind
  readonly status?: number

  constructor(kind: AdminJobsErrorKind, status?: number) {
    super(messages[kind])
    this.name = 'AdminJobsError'
    this.kind = kind
    this.status = status
  }
}