import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { Statistics, StatisticsRange } from '../types/statistics'

export async function getStatistics(range: StatisticsRange): Promise<Statistics> {
  const result = (await apiClient.get<ApiResponse<Statistics>>('/statistics', { params: range })).data
  if (result.code !== 0 || result.data === null) throw new Error(result.message)
  return result.data
}
