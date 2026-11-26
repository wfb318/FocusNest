import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { Note, NoteInput, NotePage, NoteQuery, NoteStorageMode } from '../types/note'

function data<T>(body: ApiResponse<T>): T {
  if (body.code !== 0 || body.data === null) throw new Error(body.message)
  return body.data
}
export async function listNotes(query: NoteQuery): Promise<NotePage> {
  return data((await apiClient.get<ApiResponse<NotePage>>('/notes', { params: query })).data)
}
export async function getNote(id: string): Promise<Note> {
  return data((await apiClient.get<ApiResponse<Note>>(`/notes/${id}`)).data)
}
export async function createNote(input: NoteInput): Promise<Note> {
  return data((await apiClient.post<ApiResponse<Note>>('/notes', input)).data)
}
export async function updateNote(id: string, input: NoteInput, revision: string): Promise<Note> {
  return data((await apiClient.put<ApiResponse<Note>>(`/notes/${id}`, { ...input, expected_revision: revision })).data)
}
export async function deleteNote(id: string, revision: string): Promise<void> {
  await apiClient.delete(`/notes/${id}`, { params: { revision } })
}
export async function changeNoteStorage(id: string, mode: NoteStorageMode, revision: string): Promise<Note> {
  const response = await apiClient.post<ApiResponse<Note>>(`/notes/${id}/storage`, {
    storage_mode: mode,
    expected_revision: revision,
  })
  return data(response.data)
}
