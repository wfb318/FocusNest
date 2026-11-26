import type { JournalStorage, JournalStorageOperations, JournalStorageOptions, StorageMode } from '../types/journalStorage'

export const DEFAULT_JOURNAL_STORAGE_MODE: StorageMode = 'local'
export const DEFAULT_WORKSPACE_STORAGE_MODE: StorageMode = 'cloud'

export class JournalStorageError extends Error {
  constructor(public readonly code: 'LOCAL_DIRECTORY_UNBOUND' | 'CLOUD_ENCRYPTION_UNAVAILABLE' | 'LEGACY_ACCESS_REQUIRED' | 'LEGACY_READ_ONLY' | 'SESSION_CHANGED', message: string) {
    super(message)
    this.name = 'JournalStorageError'
  }
}

export function directoryCapability(environment: { isSecureContext?: boolean; showDirectoryPicker?: unknown }): 'supported' | 'insecure' | 'unsupported' {
  if (!environment.isSecureContext) return 'insecure'
  return typeof environment.showDirectoryPicker === 'function' ? 'supported' : 'unsupported'
}

// Unavailable sources reject every operation before consulting any transport.
// Adding a real local implementation later must never introduce a cloud fallback.
export function createJournalStorage(mode: StorageMode, cloud?: JournalStorageOperations, options: JournalStorageOptions = {}): JournalStorage {
  if (mode === 'local' && options.local?.mode === 'local') return options.local
  function unavailable(): never {
    if (mode === 'local') throw new JournalStorageError('LOCAL_DIRECTORY_UNBOUND', '本地目录尚未绑定，暂时不能读取或保存日记。')
    if (mode === 'cloud_encrypted') throw new JournalStorageError('CLOUD_ENCRYPTION_UNAVAILABLE', '云端加密尚未开放，不能以普通云端保存替代。')
    throw new JournalStorageError('LEGACY_ACCESS_REQUIRED', '请通过历史云端日记的只读入口访问。')
  }
  const legacy = mode === 'cloud' && options.purpose === 'legacy-migration' && cloud && options.isCurrent
  const encrypted = mode === 'cloud_encrypted' && options.purpose === 'encrypted-journal' && cloud && options.isCurrent
  function assertCurrent() {
    if (!options.isCurrent?.()) throw new JournalStorageError('SESSION_CHANGED', '账号或页面已切换，请重新打开日记。')
  }
  async function read<T>(operation: (transport: JournalStorageOperations) => Promise<T>): Promise<T> {
    if ((!legacy && !encrypted) || !cloud) return unavailable()
    assertCurrent()
    try {
      const result = await operation(cloud)
      assertCurrent()
      return result
    } catch (error) {
      assertCurrent()
      throw error
    }
  }
  async function denyWrite(): Promise<never> {
    if (!legacy) return unavailable()
    assertCurrent()
    throw new JournalStorageError('LEGACY_READ_ONLY', '历史云端日记仅供查看和后续迁移，不能在此写入或删除。')
  }
  return {
    mode, writable: !!encrypted,
    availability: encrypted ? 'ready' : mode === 'local' ? 'unbound' : legacy ? 'legacy_read_only' : 'not_implemented',
    getDay: date => read(transport => transport.getDay(date)),
    today: () => read(transport => transport.today()),
    list: query => read(transport => transport.list(query)),
    save: encrypted ? (date, input) => read(transport => transport.save(date, input)) : denyWrite,
    delete: encrypted ? (date, revision) => read(transport => transport.delete(date, revision)) : denyWrite,
  }
}
