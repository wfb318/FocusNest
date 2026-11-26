import { parseJournalDocument, serializeJournal, validJournalDate } from './journalMarkdown'
import { LocalDirectoryError } from './localJournalStorage'
import type { Journal } from '../types/journal'
import type { TransferItem, TransferStorage } from '../types/journalTransfer'

export async function sourceDigest(entry: Journal): Promise<string> {
  const text = JSON.stringify({ entry_date: entry.entry_date, title: entry.title, content: entry.content, created_at: entry.created_at, updated_at: entry.updated_at })
  return bytesDigest(new TextEncoder().encode(text))
}
async function bytesDigest(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes as BufferSource)
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('')
}
export function matchingEntry(original: Journal, local: Journal, metadata: boolean): boolean {
  return original.entry_date === local.entry_date && original.title === local.title && original.content === local.content && (!metadata || (original.created_at === local.created_at && original.updated_at === local.updated_at))
}
function matchingDocument(item: TransferItem, document: { entry: Journal; timezone: string }): boolean {
  return matchingEntry(item.entry, document.entry, item.preserveMetadata) && (!item.preserveMetadata || item.timezone === document.timezone)
}
export async function parseImportFile(file: File, timezone: string): Promise<TransferItem> {
  if (!/\.md$/i.test(file.name) || file.size === 0 || file.size > 1024 * 1024) throw new LocalDirectoryError('INVALID_FILE', '只支持非空 UTF-8 .md 文件，单个文件最多 1 MiB。')
  const bytes = new Uint8Array(await file.arrayBuffer())
  let text: string
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes) }
  catch { throw new LocalDirectoryError('INVALID_FILE', '文件不是有效 UTF-8，没有修改原文件。') }
  if (text.includes('\0')) throw new LocalDirectoryError('INVALID_FILE', '文件包含二进制字符，未导入。')
  const filenameDate = /^(\d{4}-\d{2}-\d{2})\.md$/i.exec(file.name)?.[1] || ''
  if (filenameDate) validJournalDate(filenameDate)
  const rawHash = await bytesDigest(bytes)
  const header = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(text)
  const managed = /^focusnest_journal_version:/m.test(header ? header[1]! : text.startsWith('---\n') || text.startsWith('---\r\n') ? text.slice(0, 8192) : '')
  let entry: Journal
  if (managed) {
    const dateValue = /^entry_date: (".*")\r?$/m.exec(text)?.[1]
    let metadataDate = ''
    try { metadataDate = JSON.parse(dateValue || '') } catch { throw new LocalDirectoryError('INVALID_FILE', '平台日记日期元信息无效，请检查原文件。') }
    const document = parseJournalDocument(text, metadataDate, rawHash)
    entry = document.entry; timezone = document.timezone
    if (filenameDate && filenameDate !== entry.entry_date) throw new LocalDirectoryError('INVALID_FILE', '文件名日期与元信息冲突，请先核对原文件，未导入。')
  } else {
    const now = new Date().toISOString()
    entry = { id: '', entry_date: filenameDate, title: '', content: text, created_at: now, updated_at: now, revision: '' }
    if (filenameDate) serializeJournal(entry, timezone)
    else if (!text.trim() || [...text].length > 100000) throw new LocalDirectoryError('INVALID_FILE', '正文不能为空，最多 100000 个字符。')
  }
  return { key: `file:${rawHash}`, origin: 'file', label: file.name, entry, timezone, preserveMetadata: managed, sourceHash: '', status: entry.entry_date ? 'ready' : 'needs_date', message: entry.entry_date ? '需要检查目标日期' : '文件名没有日期，请指定日期后重新预览', serverState: 'not_applicable' }
}
export async function cloudTransferItem(entry: Journal, timezone: string): Promise<TransferItem> {
  serializeJournal(entry, timezone)
  return { key: `cloud:${entry.id}:${entry.revision}`, origin: 'cloud', label: entry.title || entry.entry_date, entry, timezone, preserveMetadata: true, sourceHash: await sourceDigest(entry), status: 'ready', message: '云端副本仍存在，需要检查本地目标', serverState: 'present' }
}
export async function previewTransfers(items: TransferItem[], storage: TransferStorage): Promise<void> {
  const counts = new Map<string, number>()
  for (const item of items) if (item.entry.entry_date) counts.set(item.entry.entry_date, (counts.get(item.entry.entry_date) || 0) + 1)
  for (const item of items) {
    item.localRevision = undefined
    item.progressRecorded = false
    if (item.parseError) { item.status = 'error'; item.message = item.parseError; continue }
    if (!item.entry.entry_date) { item.status = 'needs_date'; item.message = '请先指定导入日期，再重新预览；不会自动使用今天'; continue }
    try {
      serializeJournal(item.entry, item.timezone)
      if ((counts.get(item.entry.entry_date) || 0) > 1) { item.status = 'conflict'; item.message = '本批次有多篇指向同一天，请移除重复项再预览'; continue }
      item.sourceHash = await sourceDigest(item.entry)
      const document = await storage.readDocument(item.entry.entry_date)
      if (!document) { item.status = 'ready'; item.message = '目标不存在，可新建本地副本' }
      else if (matchingDocument(item, document)) { item.status = 'verified'; item.localRevision = document.entry.revision; item.message = '本地已有一致内容，保留原文件，不重复写入' }
      else { item.status = 'conflict'; item.message = '本地已有不同内容或时间元信息，停止覆盖；可跳过该篇' }
    } catch (error) {
      item.status = item.entry.entry_date ? 'error' : 'needs_date'
      item.message = error instanceof LocalDirectoryError ? error.message : '无法检查本地目标，请检查文件格式或权限'
    }
  }
}
export async function copyAndVerify(item: TransferItem, storage: TransferStorage): Promise<Journal> {
  serializeJournal(item.entry, item.timezone)
  let document = await storage.readDocument(item.entry.entry_date)
  if (!document) {
    try { await storage.importEntry(item.entry, item.timezone) }
    catch (error) { if (!(error instanceof LocalDirectoryError) || error.code !== 'FILE_CONFLICT') throw error }
    document = await storage.readDocument(item.entry.entry_date)
  }
  if (!document || !matchingDocument(item, document)) throw new LocalDirectoryError('FILE_CONFLICT', '目标内容或元信息已经变化，未覆盖；不能将此篇标记为迁移成功。')
  const local = document.entry
  item.status = 'verified'; item.localRevision = local.revision
  item.message = '本地文件已逐项读回校验，来源原件保留'
  return local
}
export async function verifyBeforeCleanup(item: TransferItem, storage: TransferStorage, readCloud: () => Promise<Journal | null>) {
  if (item.origin !== 'cloud' || item.status !== 'verified' || !item.localRevision) throw new LocalDirectoryError('INVALID_FILE', '请先完成本地迁移及校验。')
  async function readVerified() {
    const document = await storage.readDocument(item.entry.entry_date)
    if (!document || document.entry.revision !== item.localRevision || !matchingDocument(item, document)) throw new LocalDirectoryError('FILE_CONFLICT', '本地文件已更改或不存在，停止清理云端副本。')
    return document.entry
  }
  await readVerified()
  const original = await readCloud()
  if (original && (original.id !== item.entry.id || original.revision !== item.entry.revision || await sourceDigest(original) !== item.sourceHash)) throw new LocalDirectoryError('FILE_CONFLICT', '云端原件版本已改变，请重新预览；未清理云端。')
  // Cloud access may take time; reject local edits made while waiting for it.
  const local = await readVerified()
  return { missing: !original, expected_revision: item.entry.revision, verified_source_digest: item.sourceHash, local_revision: local.revision, confirmation: 'DELETE_CLOUD_COPY' as const }
}
