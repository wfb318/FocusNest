export interface ApiResponse<T> {
  code: number
  message: string
  data: T | null
}

export interface HealthStatus {
  status: 'ok'
  database: 'not_checked' | 'connected'
}
