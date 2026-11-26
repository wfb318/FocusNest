import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { Journal, JournalDay, JournalInput, JournalPage, JournalQuery } from '../types/journal'
import type { JournalStorageOperations } from '../types/journalStorage'

function data<T>(body: ApiResponse<T>): T {
  if (body.code !== 0 || body.data === null) throw new Error(body.message)
  return body.data
}
async function getJournal(date: string): Promise<JournalDay> {
  return data((await apiClient.get<ApiResponse<JournalDay>>(`/journals/${date}`, { headers: { 'X-FocusNest-Journal-Access': 'legacy-migration' } })).data)
}
async function todayJournal(): Promise<JournalDay> {
  return data((await apiClient.get<ApiResponse<JournalDay>>('/journals/today', { headers: { 'X-FocusNest-Journal-Access': 'legacy-migration' } })).data)
}
async function listJournals(query: JournalQuery): Promise<JournalPage> {
  return data((await apiClient.get<ApiResponse<JournalPage>>('/journals', { params: query, headers: { 'X-FocusNest-Journal-Access': 'legacy-migration' } })).data)
}
async function saveJournal(date: string, input: JournalInput): Promise<Journal> {
  return data((await apiClient.put<ApiResponse<Journal>>(`/journals/${date}`, input)).data)
}
async function deleteJournal(date: string, revision: string): Promise<void> {
  await apiClient.delete(`/journals/${date}`, { params: { revision } })
}

// HTTP transport only. Pages use createJournalStorage to enforce source policy.
export const cloudJournalTransport: JournalStorageOperations = {
  getDay: getJournal, today: todayJournal, list: listJournals, save: saveJournal, delete: deleteJournal,
}
const encryptedPath = '/journals/encrypted'
const encryptedAccess = { headers: { 'X-FocusNest-Journal-Access': 'cloud-encrypted' } }

export const encryptedJournalTransport: JournalStorageOperations = {
  async getDay(date) {
    return data((await apiClient.get<ApiResponse<JournalDay>>(`${encryptedPath}/${date}`, encryptedAccess)).data)
  },
  async today() {
    return data((await apiClient.get<ApiResponse<JournalDay>>(`${encryptedPath}/today`, encryptedAccess)).data)
  },
  async list({ page, page_size, start_date, end_date }) {
    const params = { page, page_size, start_date, end_date }
    return data((await apiClient.get<ApiResponse<JournalPage>>(encryptedPath, { ...encryptedAccess, params })).data)
  },
  async save(date, input) {
    return data((await apiClient.put<ApiResponse<Journal>>(`${encryptedPath}/${date}`, input, encryptedAccess)).data)
  },
  async delete(date, revision) {
    await apiClient.delete(`${encryptedPath}/${date}`, { ...encryptedAccess, params: { revision } })
  },
}
export async function removeMigratedCloudCopy(date: string, payload: { expected_revision: string; verified_source_digest: string; local_revision: string; confirmation: 'DELETE_CLOUD_COPY' }) {
  return data((await apiClient.post<ApiResponse<{ removed: boolean; already_missing: boolean }>>(`/journals/${date}/migration-cleanup`, payload, { headers: { 'X-FocusNest-Journal-Access': 'legacy-migration' } })).data)
}
