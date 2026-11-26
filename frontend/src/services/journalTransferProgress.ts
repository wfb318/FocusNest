import { directoryLock, readLocalFile, writeLocalFile, LocalDirectoryError } from './localJournalStorage'
import type { DirectoryLock } from './localJournalStorage'
import type { JournalConnection } from '../types/localJournal'
import type { TransferRecord } from '../types/journalTransfer'

const hash = /^[a-f0-9]{64}$/
export function createTransferProgress(connection: JournalConnection, userId: string, lock: DirectoryLock = directoryLock) {
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(userId)) throw new LocalDirectoryError('INVALID_FILE', '账号标识无效，未创建迁移进度。')
  const name = `FocusNest-migration-${userId}.json`
  async function read() {
    let snapshot
    try { snapshot = await readLocalFile(connection.handle, name, connection.isCurrent) }
    catch (error) { if (error instanceof Error && error.name === 'NotFoundError') return { records: [] as TransferRecord[], revision: null }; throw error }
    let value
    try { value = JSON.parse(snapshot.text) }
    catch { throw new LocalDirectoryError('INVALID_FILE', '迁移进度文件不是有效 JSON，未覆盖；请检查原文件。') }
    if (value?.version !== 1 || value?.userId !== userId || !Array.isArray(value.records) || value.records.length > 2000) throw new LocalDirectoryError('INVALID_FILE', '迁移进度文件格式无效，未覆盖；可以根据现有日记重新预览。')
    for (const item of value.records) {
      if (!item || typeof item.key !== 'string' || !['file', 'cloud'].includes(item.origin) || !hash.test(item.sourceHash) || !hash.test(item.localRevision) || typeof item.sourceRevision !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(item.targetDate) || !['verified', 'cloud_removed'].includes(item.state) || typeof item.verifiedAt !== 'string') throw new LocalDirectoryError('INVALID_FILE', '迁移进度记录无效，未覆盖。')
    }
    return { records: value.records as TransferRecord[], revision: snapshot.revision }
  }
  async function save(record: TransferRecord) {
    await lock(async () => {
      const data = await read()
      const records = data.records.filter(item => item.key !== record.key)
      records.push(record)
      if (records.length > 2000) throw new LocalDirectoryError('INVALID_FILE', '进度记录超过 2000 条，未覆盖进度文件。')
      const text = JSON.stringify({ version: 1, userId, records }, null, 2)
      await writeLocalFile(connection.handle, name, text, data.revision, connection.isCurrent, operation => operation())
    })
  }
  return { name, read, save }
}
