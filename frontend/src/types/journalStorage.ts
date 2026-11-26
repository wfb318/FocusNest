import type { Journal, JournalDay, JournalInput, JournalPage, JournalQuery } from './journal'

export type StorageMode = 'cloud' | 'cloud_encrypted' | 'local'
export type JournalStorageAvailability = 'unbound' | 'not_implemented' | 'legacy_read_only' | 'ready'

export interface JournalStorageOperations {
  getDay(date: string): Promise<JournalDay>
  today(): Promise<JournalDay>
  list(query: JournalQuery): Promise<JournalPage>
  save(date: string, input: JournalInput): Promise<Journal>
  delete(date: string, revision: string): Promise<void>
}

export interface JournalStorage extends JournalStorageOperations {
  readonly mode: StorageMode
  readonly availability: JournalStorageAvailability
  readonly writable: boolean
}

export interface JournalStorageOptions {
  local?: JournalStorage
  purpose?: 'legacy-migration' | 'encrypted-journal'
  // A caller must bind legacy reads to the account and lifetime that opened them.
  isCurrent?: () => boolean
}
