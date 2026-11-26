import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { Dashboard } from '../types/dashboard'
export async function getDashboard(): Promise<Dashboard> {
  // The default journal source is local. Never fetch a legacy journal title here.
  const result = (await apiClient.get<ApiResponse<Dashboard>>('/dashboard', { params: { include_journal: false } })).data
  if (!result.data) throw new Error(result.message)
  return result.data
}
