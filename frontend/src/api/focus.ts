import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { FocusAction, FocusInput, FocusPage, FocusSession } from '../types/focus'

export async function currentFocus(): Promise<FocusSession | null> {
  return (await apiClient.get<ApiResponse<FocusSession>>('/focus/current')).data.data
}
export async function focusHistory(page: number): Promise<FocusPage> {
  const result = (await apiClient.get<ApiResponse<FocusPage>>('/focus/sessions', { params: { page, page_size: 10 } })).data
  if (!result.data) throw new Error(result.message)
  return result.data
}
export async function startFocus(input: FocusInput): Promise<FocusSession> {
  const result = (await apiClient.post<ApiResponse<FocusSession>>('/focus/sessions', input)).data
  if (!result.data) throw new Error(result.message)
  return result.data
}
export async function changeFocus(id: string, action: FocusAction): Promise<FocusSession> {
  const result = (await apiClient.post<ApiResponse<FocusSession>>(`/focus/sessions/${id}/${action}`)).data
  if (!result.data) throw new Error(result.message)
  return result.data
}
