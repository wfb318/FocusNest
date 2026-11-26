export type NoteStorageMode = 'cloud' | 'cloud_encrypted'
export interface NoteInput {
  title: string
  content: string
  pinned: boolean
  folder_id: string | null
  problem_id?: string | null
  storage_mode?: NoteStorageMode
}
export interface NoteSummary {
  id: string
  title: string
  storage_mode: NoteStorageMode
  pinned: boolean
  folder_id: string | null
  problem_id: string | null
  revision: string
  created_at: string
  updated_at: string
}
export interface Note extends NoteSummary { content: string }
export interface NotePage { items: NoteSummary[]; total: number; page: number; page_size: number }
export interface NoteQuery { page: number; page_size: number; q?: string; pinned?: boolean; folder_id?: string; unfiled?: boolean }
