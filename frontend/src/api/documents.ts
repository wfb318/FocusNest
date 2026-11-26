import axios from 'axios'
import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { DocumentPage, DocumentQuery, DocumentStorageMode, WorkspaceDocument } from '../types/document'

function data<T>(body: ApiResponse<T>): T {
  if (body.code !== 0 || body.data === null) throw new Error(body.message)
  return body.data
}
export async function listDocuments(query: DocumentQuery): Promise<DocumentPage> {
  return data((await apiClient.get<ApiResponse<DocumentPage>>('/documents', { params: query })).data)
}
export async function getDocument(id: string): Promise<WorkspaceDocument> {
  return data((await apiClient.get<ApiResponse<WorkspaceDocument>>(`/documents/${id}`)).data)
}
export async function uploadDocument(file: File, mode: DocumentStorageMode): Promise<WorkspaceDocument> {
  if (mode === 'cloud_encrypted') {
    const response = await apiClient.post<ApiResponse<WorkspaceDocument>>('/documents/encrypted-upload', file, {
      headers: { 'Content-Type': 'application/octet-stream', 'X-FocusNest-Filename': encodeURIComponent(file.name) },
    })
    return data(response.data)
  }
  const form = new FormData()
  form.append('file', file)
  return data((await apiClient.post<ApiResponse<WorkspaceDocument>>('/documents', form)).data)
}
export async function changeDocumentStorage(id: string, mode: DocumentStorageMode, revision: string): Promise<WorkspaceDocument> {
  const response = await apiClient.post<ApiResponse<WorkspaceDocument>>(`/documents/${id}/storage`, {
    storage_mode: mode,
    expected_revision: revision,
  })
  return data(response.data)
}
export async function renameDocument(id: string, title: string, revision: string): Promise<WorkspaceDocument> {
  return data((await apiClient.patch<ApiResponse<WorkspaceDocument>>(`/documents/${id}`, { title, expected_revision: revision })).data)
}
export async function deleteDocument(id: string, revision: string): Promise<void> {
  await apiClient.delete(`/documents/${id}`, { params: { revision } })
}
async function binary(url: string): Promise<Blob> {
  try {
    return (await apiClient.get<Blob>(url, { responseType: 'blob' })).data
  } catch (cause) {
    // Error responses remain JSON even though a successful download is binary.
    if (axios.isAxiosError(cause) && cause.response?.data instanceof Blob) {
      try { cause.response.data = JSON.parse(await cause.response.data.text()) } catch { /* Use generic transport error. */ }
    }
    throw cause
  }
}

export function downloadDocument(id: string): Promise<Blob> { return binary(`/documents/${id}/download`) }
export function getPdfPage(id: string, page: number): Promise<Blob> { return binary(`/documents/${id}/preview?page=${page}`) }
