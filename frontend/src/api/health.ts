import { apiClient } from './client'
import type { ApiResponse, HealthStatus } from '../types/api'

export async function getHealth(checkDatabase = false): Promise<HealthStatus> {
  const { data } = await apiClient.get<ApiResponse<HealthStatus>>('/health', {
    params: { check_database: checkDatabase },
  })
  if (data.code !== 0 || !data.data) throw new Error(data.message)
  return data.data
}
