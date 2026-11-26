export type DocumentKind = 'markdown' | 'text' | 'pdf' | 'word' | 'presentation' | 'spreadsheet'
export type DocumentStorageMode = 'cloud' | 'cloud_encrypted'
export interface DocumentPreview { sections: { title: string; paragraphs: string[]; rows: string[][] }[]; pages: number; truncated: boolean }
export interface DocumentSummary {
  id: string
  title: string
  filename: string
  storage_mode: DocumentStorageMode
  kind: DocumentKind
  size_bytes: number
  revision: string
  created_at: string
  updated_at: string
}
export interface WorkspaceDocument extends DocumentSummary { content: string; preview: DocumentPreview | null }
export interface DocumentPage { items: DocumentSummary[]; total: number; page: number; page_size: number }
export interface DocumentQuery { page: number; page_size: number; q?: string; kind?: DocumentKind }
