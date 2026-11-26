import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { AdminOverview, AdminUserPage, AdminUserQuery } from '../types/admin'

function unwrap<T>(response: ApiResponse<T>): T {
  if (response.code !== 0 || response.data === null) throw new Error(response.message)
  return response.data
}
export async function getAdminOverview() {
  return unwrap((await apiClient.get<ApiResponse<AdminOverview>>('/admin/overview')).data)
}
export async function getAdminUsers(params: AdminUserQuery) {
  return unwrap((await apiClient.get<ApiResponse<AdminUserPage>>('/admin/users', { params })).data)
}
