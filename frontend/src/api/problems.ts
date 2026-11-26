import axios from 'axios'
import { apiClient } from './client'
import type { ApiResponse } from '../types/api'

export type ProblemBucket = 'today' | 'history' | 'resolved' | 'all'
export interface Problem {
  id: string; content: string; is_resolved: boolean; resolved_at: string | null
  revision: string; created_at: string; updated_at: string
}
export interface ProblemPage {
  items: Problem[]; total: number; page: number; page_size: number
  counts: Record<ProblemBucket, number>; today: string; timezone: string
}
export async function listProblems(bucket: ProblemBucket, q: string, page: number): Promise<ProblemPage> {
  return (await apiClient.get<ApiResponse<ProblemPage>>('/problems', { params: { bucket, q: q || undefined, page, page_size: 20 } })).data.data!
}
export async function createProblem(content: string) { await apiClient.post('/problems', { content }) }
export async function getProblem(id: string): Promise<Problem> {
  return (await apiClient.get<ApiResponse<Problem>>(`/problems/${id}`)).data.data!
}
export async function editProblem(item: Problem, content: string) { await apiClient.put(`/problems/${item.id}`, { content, expected_revision: item.revision }) }
export async function setProblemStatus(item: Problem) { await apiClient.patch(`/problems/${item.id}/status`, { is_resolved: !item.is_resolved, expected_revision: item.revision }) }
export async function exportProblems(bucket: ProblemBucket, q: string): Promise<Blob> {
  try { return (await apiClient.get<Blob>('/problems/export', { params: { bucket, q: q || undefined }, responseType: 'blob' })).data }
  catch (cause) {
    if (axios.isAxiosError(cause) && cause.response?.data instanceof Blob) {
      try { cause.response.data = JSON.parse(await cause.response.data.text()) } catch { /* Use transport error. */ }
    }
    throw cause
  }
}
