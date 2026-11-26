import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { LoginInput, Registration, TokenResponse, User, ProfileUpdate } from '../types/auth'

function unwrap<T>(response: ApiResponse<T>): T {
  if (response.code !== 0 || response.data === null) throw new Error(response.message)
  return response.data
}
export async function registerAccount(input: Registration) {
  return unwrap((await apiClient.post<ApiResponse<User>>('/auth/register', input)).data)
}
export async function loginAccount(input: LoginInput) {
  return unwrap((await apiClient.post<ApiResponse<TokenResponse>>('/auth/login', input)).data)
}
export async function refreshAccount() {
  return unwrap((await apiClient.post<ApiResponse<TokenResponse>>('/auth/refresh')).data)
}
export async function logoutAccount() { await apiClient.post('/auth/logout') }
export async function updateAccount(input: ProfileUpdate) {
  return unwrap((await apiClient.patch<ApiResponse<User>>('/users/me', input)).data)
}
export async function getAccount() {
  return unwrap((await apiClient.get<ApiResponse<User>>('/users/me')).data)
}
export async function sendHeartbeat() {
  await apiClient.post('/users/me/heartbeat', {})
}
