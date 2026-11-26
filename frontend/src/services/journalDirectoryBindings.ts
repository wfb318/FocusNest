import type { DirectoryBindings, JournalDirectoryHandle } from '../types/localJournal'

function validHandle(value: unknown): value is JournalDirectoryHandle {
  const handle = value as Partial<JournalDirectoryHandle> | undefined
  return handle?.kind === 'directory' && typeof handle.name === 'string' && typeof handle.getFileHandle === 'function' && typeof handle.queryPermission === 'function' && typeof handle.requestPermission === 'function'
}
function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    let blocked = false
    const request = indexedDB.open('focusnest-journal-storage', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('directories')
    request.onerror = () => reject(new Error('Cannot open directory bindings'))
    request.onblocked = () => { blocked = true; reject(new Error('Directory bindings blocked')) }
    request.onsuccess = () => {
      if (blocked) { request.result.close(); return }
      request.result.onversionchange = () => request.result.close()
      resolve(request.result)
    }
  })
}
async function access(userId: string, signal: AbortSignal, operation: 'load' | 'save' | 'remove', handle?: JournalDirectoryHandle): Promise<JournalDirectoryHandle | undefined> {
  if (!userId || signal.aborted) throw new Error('Inactive account')
  const db = await openDatabase()
  try {
    if (signal.aborted) throw new Error('Inactive account')
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction('directories', operation === 'load' ? 'readonly' : 'readwrite')
      const abort = () => { try { transaction.abort() } catch { /* Already completed. */ } }
      signal.addEventListener('abort', abort, { once: true })
      const store = transaction.objectStore('directories')
      const request = operation === 'load' ? store.get(userId) : operation === 'save' ? store.put({ version: 1, handle }, userId) : store.delete(userId)
      transaction.oncomplete = () => {
        signal.removeEventListener('abort', abort)
        if (signal.aborted) { reject(new Error('Inactive account')); return }
        const value = operation === 'load' ? request.result : undefined
        if (value !== undefined && (!value || typeof value !== 'object' || value.version !== 1 || !validHandle(value.handle))) { reject(new Error('Invalid directory binding')); return }
        resolve(value?.handle)
      }
      transaction.onerror = transaction.onabort = () => {
        signal.removeEventListener('abort', abort)
        reject(new Error('Directory binding operation failed'))
      }
    })
  } finally { db.close() }
}
export const directoryBindings: DirectoryBindings = {
  load: (userId, signal) => access(userId, signal, 'load'),
  save: async (userId, handle, signal) => { await access(userId, signal, 'save', handle) },
  remove: async (userId, signal) => { await access(userId, signal, 'remove') },
}
