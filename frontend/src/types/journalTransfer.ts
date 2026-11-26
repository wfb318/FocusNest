import type { Journal } from './journal'
import type { JournalStorage } from './journalStorage'
export interface TransferStorage extends JournalStorage {
  importEntry(entry: Journal, timezone: string): Promise<Journal>
  readDocument(date: string): Promise<{ entry: Journal; timezone: string } | null>
}
export interface TransferItem {
  key: string
  origin: 'file' | 'cloud'
  label: string
  entry: Journal
  timezone: string
  preserveMetadata: boolean
  sourceHash: string
  status: 'needs_date' | 'ready' | 'conflict' | 'verified' | 'error'
  message: string
  parseError?: string
  localRevision?: string
  progressRecorded?: boolean
  serverState: 'not_applicable' | 'present' | 'removed' | 'unknown'
}
export interface TransferRecord {
  key: string
  origin: 'file' | 'cloud'
  sourceHash: string
  sourceRevision: string
  targetDate: string
  localRevision: string
  verifiedAt: string
  state: 'verified' | 'cloud_removed'
}
