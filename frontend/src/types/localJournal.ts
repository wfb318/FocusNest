export interface LocalFileWriter {
  write(data: string): Promise<void>
  close(): Promise<void>
  abort(): Promise<void>
}
export interface LocalFileHandle {
  getFile(): Promise<File>
  createWritable(options?: { mode?: 'exclusive' }): Promise<LocalFileWriter>
}
export interface JournalDirectoryHandle {
  readonly kind: 'directory'
  readonly name: string
  queryPermission(options: { mode: 'readwrite' }): Promise<PermissionState>
  requestPermission(options: { mode: 'readwrite' }): Promise<PermissionState>
  getFileHandle(name: string, options?: { create?: boolean }): Promise<LocalFileHandle>
  getDirectoryHandle?(name: string, options?: { create?: boolean }): Promise<JournalDirectoryHandle>
  values?(): AsyncIterable<{ kind: string; name: string }>
  removeEntry?(name: string): Promise<void>
}
export interface DirectoryBindings {
  load(userId: string, signal: AbortSignal): Promise<JournalDirectoryHandle | undefined>
  save(userId: string, handle: JournalDirectoryHandle, signal: AbortSignal): Promise<void>
  remove(userId: string, signal: AbortSignal): Promise<void>
}
export type DirectoryStatus = 'signed_out' | 'unbound' | 'restoring' | 'permission_required' | 'ready' | 'unavailable'
export interface DirectoryState {
  bindingVersion: number
  status: DirectoryStatus
  directoryName: string
  busy: boolean
  error: string
  notice: string
  probeName: string
  probeDraft: string
  probeSaved: boolean
}
export interface LocalFileSnapshot { text: string; revision: string }
export interface JournalConnection { handle: JournalDirectoryHandle; isCurrent: () => boolean }
