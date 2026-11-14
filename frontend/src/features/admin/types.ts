export type JobKind = 'ingestion' | 'indexing'

export type JobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'

export interface JobProgress {
  unit: 'assets'
  processed: number | null
  total: number | null
  percent: number | null
}

export interface JobResult {
  persistence: 'postgresql' | 'local_files_only' | null
  input_count: number | null
  succeeded: number | null
  failed: number | null
  skipped: number | null
  manifest_sha256: string | null
  exit_code: number | null
}

export interface JobError {
  code: string
  message: string
}

export interface JobMetadata {
  job_id: string
  kind: JobKind
  runner: string
  status: JobStatus
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
  progress: JobProgress
  result: JobResult | null
  error: JobError | null
}

export interface JobsPagination {
  page: number
  limit: number
  total: number
  pages: number
  has_next: boolean
}

export interface JobListResponse {
  items: JobMetadata[]
  pagination: JobsPagination
  mock: false
}

export interface JobDetailResponse {
  job: JobMetadata
  mock: false
}

export interface JobListQuery {
  kind?: JobKind
  status?: JobStatus
  page?: number
  limit?: number
}