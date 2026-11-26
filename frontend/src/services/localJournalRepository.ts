import { directoryLock, LocalDirectoryError, readLocalFile, writeLocalFile } from './localJournalStorage'
import { parseJournal, parseJournalDocument, serializeJournal, validJournalDate } from './journalMarkdown'
import { dateInZone } from '../utils/scheduleTime'
import type { Journal, JournalPage, JournalQuery } from '../types/journal'
import type { TransferStorage } from '../types/journalTransfer'
import type { JournalConnection, JournalDirectoryHandle } from '../types/localJournal'
import type { DirectoryLock } from './localJournalStorage'

function missing(error: unknown) { return error instanceof Error && error.name === 'NotFoundError' }
export function createLocalJournalRepository(connection: JournalConnection, zone: () => string, lock: DirectoryLock = directoryLock): TransferStorage {
  function assertCurrent() { if (!connection.isCurrent()) throw new LocalDirectoryError('SESSION_CHANGED', '账号或目录已改变，旧日记操作已停止；请重新载入。') }
  async function permit() {
    assertCurrent()
    const permission = await connection.handle.queryPermission({ mode: 'readwrite' })
    assertCurrent()
    if (permission !== 'granted') throw new LocalDirectoryError('PERMISSION_REQUIRED', '目录权限已失效，请重新授权。页面输入仍保留。')
  }
  async function folder(date: string, create = false): Promise<JournalDirectoryHandle> {
    validJournalDate(date); await permit()
    let result = connection.handle
    for (const part of [date.slice(0, 4), date.slice(5, 7)]) {
      if (!result.getDirectoryHandle) throw new LocalDirectoryError('INVALID_FILE', '当前目录不支持子文件夹访问。')
      result = await result.getDirectoryHandle(part, { create }); assertCurrent()
    }
    return result
  }
  async function readDocument(date: string) {
    try {
      const parent = await folder(date)
      const file = await readLocalFile(parent, `${date}.md`, connection.isCurrent)
      return parseJournalDocument(file.text, date, file.revision)
    } catch (error) {
      assertCurrent()
      if (missing(error)) return null
      throw error
    }
  }
  async function getDay(date: string) { return { entry_date: date, entry: (await readDocument(date))?.entry || null } }
  async function list(query: JournalQuery): Promise<JournalPage> {
    await permit()
    if (query.start_date) validJournalDate(query.start_date)
    if (query.end_date) validJournalDate(query.end_date)
    if (!Number.isInteger(query.page) || query.page < 1 || !Number.isInteger(query.page_size) || query.page_size < 1 || query.page_size > 100 || (query.start_date && query.end_date && query.start_date > query.end_date)) throw new LocalDirectoryError('INVALID_FILE', '请检查日期范围和分页参数。')
    const dates: string[] = []
    let visited = 0
    async function children(parent: JournalDirectoryHandle, pattern: RegExp, kind: string) {
      if (!parent.values) throw new LocalDirectoryError('INVALID_FILE', '当前目录不支持列举文件。')
      const names: string[] = []
      for await (const item of parent.values()) {
        assertCurrent()
        if (++visited > 10000) throw new LocalDirectoryError('INVALID_FILE', '目录条目过多，请选择专用日记目录。')
        if (item.kind === kind && pattern.test(item.name)) names.push(item.name)
      }
      return names
    }
    for (const year of await children(connection.handle, /^[1-9]\d{3}$/, 'directory')) {
      const yearly = await connection.handle.getDirectoryHandle!(year); assertCurrent()
      for (const month of await children(yearly, /^(0[1-9]|1[0-2])$/, 'directory')) {
        const monthly = await yearly.getDirectoryHandle!(month); assertCurrent()
        for (const name of await children(monthly, /^\d{4}-\d{2}-\d{2}\.md$/, 'file')) {
          const date = validJournalDate(name.slice(0, -3))
          if (date.slice(0, 7) !== `${year}-${month}`) throw new LocalDirectoryError('INVALID_FILE', '日记日期与所在年月目录不一致，请检查目录。')
          if ((!query.start_date || date >= query.start_date) && (!query.end_date || date <= query.end_date)) dates.push(date)
          if (dates.length > 2000) throw new LocalDirectoryError('INVALID_FILE', '当前查询超过 2000 篇，请缩小日期范围。')
        }
      }
    }
    const items: JournalPage['items'] = [], keyword = query.q?.toLocaleLowerCase() || ''
    for (const date of dates.sort().reverse()) {
      const { entry } = await getDay(date)
      if (entry && (!keyword || `${entry.title}\n${entry.content}`.toLocaleLowerCase().includes(keyword))) {
        const { content: _content, ...summary } = entry
        items.push(summary)
      }
    }
    assertCurrent()
    return { items: items.slice((query.page - 1) * query.page_size, query.page * query.page_size), total: items.length, page: query.page, page_size: query.page_size }
  }
  return {
    mode: 'local', availability: 'ready', writable: true, getDay, readDocument, today: () => getDay(dateInZone(Date.now(), zone())), list,
    async importEntry(entry, timezone) {
      return lock(async () => {
        validJournalDate(entry.entry_date)
        if ((await getDay(entry.entry_date)).entry) throw new LocalDirectoryError('FILE_CONFLICT', '目标日期已有文件，导入不会覆盖。请重新预览冲突。')
        const text = serializeJournal(entry, timezone)
        const parent = await folder(entry.entry_date, true)
        const result = await writeLocalFile(parent, `${entry.entry_date}.md`, text, null, connection.isCurrent, operation => operation())
        return parseJournal(result.text, entry.entry_date, result.revision)
      })
    },
    async save(date, input) {
      return lock(async () => {
        const original = (await getDay(date)).entry
        if ((original?.revision ?? null) !== input.expected_revision) throw new LocalDirectoryError('FILE_CONFLICT', '磁盘版本已改变，输入仍保留，请重新读取后再决定。')
        const now = new Date().toISOString()
        const entry: Journal = { id: `local:${date}`, entry_date: date, title: input.title.trim(), content: input.content, created_at: original?.created_at || now, updated_at: now, revision: '' }
        const text = serializeJournal(entry, zone())
        const parent = await folder(date, true)
        // The outer lock spans read/validate/write. Do not acquire the same Web Lock twice.
        const result = await writeLocalFile(parent, `${date}.md`, text, input.expected_revision, connection.isCurrent, operation => operation())
        return parseJournal(result.text, date, result.revision)
      })
    },
    async delete(date, revision) {
      await lock(async () => {
        const original = (await getDay(date)).entry
        if (!original || original.revision !== revision) throw new LocalDirectoryError('FILE_CONFLICT', '文件已经修改或删除，未执行删除，请重新读取。')
        const parent = await folder(date)
        const latest = await readLocalFile(parent, `${date}.md`, connection.isCurrent)
        if (latest.revision !== revision) throw new LocalDirectoryError('FILE_CONFLICT', '文件版本已改变，未执行删除。')
        assertCurrent()
        if (!parent.removeEntry) throw new LocalDirectoryError('INVALID_FILE', '当前浏览器不能删除此文件。')
        await parent.removeEntry(`${date}.md`); assertCurrent()
      })
    },
  }
}
