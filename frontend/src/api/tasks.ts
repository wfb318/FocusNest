import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { Task, TaskInput, TaskPage, TaskQuery } from '../types/task'

function unwrap<T>(body: ApiResponse<T>): T {
  if (body.code !== 0 || body.data === null) throw new Error(body.message)
  return body.data
}

export async function listTasks(query: TaskQuery): Promise<TaskPage> {
  return unwrap((await apiClient.get<ApiResponse<TaskPage>>('/tasks', { params: query })).data)
}
export async function getTask(id: string): Promise<Task> {
  return unwrap((await apiClient.get<ApiResponse<Task>>(`/tasks/${id}`)).data)
}
export async function createTask(input: TaskInput): Promise<Task> {
  return unwrap((await apiClient.post<ApiResponse<Task>>('/tasks', input)).data)
}
export async function updateTask(id: string, input: Partial<TaskInput>): Promise<Task> {
  return unwrap((await apiClient.patch<ApiResponse<Task>>(`/tasks/${id}`, input)).data)
}
export async function completeTask(id: string): Promise<Task> {
  return unwrap((await apiClient.post<ApiResponse<Task>>(`/tasks/${id}/complete`)).data)
}
export async function deleteTask(id: string): Promise<void> {
  await apiClient.delete(`/tasks/${id}`)
}
