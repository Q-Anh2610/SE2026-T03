export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export type AdminJob = {
  id: string
  type: 'ingestion' | 'indexing'
  status: JobStatus
  createdAt: string
  updatedAt: string
  progress?: number
  result?: string
  error?: string
}

export const adminJobFixtures: AdminJob[] = [
  {
    id: 'job-ingestion-001',
    type: 'ingestion',
    status: 'queued',
    createdAt: '2026-10-25T08:00:00Z',
    updatedAt: '2026-10-25T08:00:00Z',
  },
  {
    id: 'job-indexing-002',
    type: 'indexing',
    status: 'running',
    createdAt: '2026-10-25T07:30:00Z',
    updatedAt: '2026-10-25T08:15:00Z',
    progress: 62,
  },
  {
    id: 'job-ingestion-003',
    type: 'ingestion',
    status: 'succeeded',
    createdAt: '2026-10-24T14:00:00Z',
    updatedAt: '2026-10-24T14:20:00Z',
    result: 'Đã xử lý 200 asset',
  },
  {
    id: 'job-indexing-004',
    type: 'indexing',
    status: 'failed',
    createdAt: '2026-10-24T12:00:00Z',
    updatedAt: '2026-10-24T12:05:00Z',
    error: 'Không thể kết nối tới vector store',
  },
]

export const emptyAdminJobFixtures: AdminJob[] = []