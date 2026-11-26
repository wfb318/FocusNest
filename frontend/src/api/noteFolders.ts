import { apiClient } from './client'
import type { ApiResponse } from '../types/api'

export interface NoteFolder { id: string; parent_id: string | null; name: string; revision: string }
function data<T>(body: ApiResponse<T>): T {
  if (body.code !== 0 || body.data === null) throw new Error(body.message)
  return body.data
}
export async function listFolders(): Promise<NoteFolder[]> {
  return data((await apiClient.get<ApiResponse<NoteFolder[]>>('/note-folders')).data)
}
export async function createFolder(name: string, parent_id: string | null): Promise<NoteFolder> {
  return data((await apiClient.post<ApiResponse<NoteFolder>>('/note-folders', { name, parent_id })).data)
}
export async function renameFolder(folder: NoteFolder, name: string): Promise<NoteFolder> {
  return data((await apiClient.patch<ApiResponse<NoteFolder>>(`/note-folders/${folder.id}`, { name, expected_revision: folder.revision })).data)
}
export async function deleteFolder(folder: NoteFolder): Promise<void> {
  await apiClient.delete(`/note-folders/${folder.id}`, { params: { revision: folder.revision } })
}
