import { LocalDirectoryError } from './localJournalStorage'
import type { Journal } from '../types/journal'

function invalid(): never { throw new LocalDirectoryError('INVALID_FILE', '日记文件格式、日期或内容无效，未覆盖原文件。请检查本地文件或通过导入功能处理。') }
export function validJournalDate(date: string): string {
  if (!/^[1-9]\d{3}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(`${date}T12:00:00Z`)) || new Date(`${date}T12:00:00Z`).toISOString().slice(0, 10) !== date) return invalid()
  return date
}
function validate(entry: Pick<Journal, 'entry_date' | 'title' | 'content' | 'created_at' | 'updated_at'>, zone: string) {
  validJournalDate(entry.entry_date)
  if (typeof entry.title !== 'string' || typeof entry.content !== 'string') invalid()
  if ([...entry.title].length > 200) throw new LocalDirectoryError('INVALID_FILE', '日记标题最多 200 个字符，输入未保存。')
  if (!entry.content.trim() || [...entry.content].length > 100000) throw new LocalDirectoryError('INVALID_FILE', '日记正文不能为空，最多 100000 个字符；输入仍保留。')
  for (const time of [entry.created_at, entry.updated_at]) {
    if (typeof time !== 'string' || !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(time) || !Number.isFinite(Date.parse(time))) invalid()
  }
  try { new Intl.DateTimeFormat('en', { timeZone: zone }).format() } catch { invalid() }
}
export function serializeJournal(entry: Journal, zone: string): string {
  validate(entry, zone)
  return ['---', 'focusnest_journal_version: 1', ...Object.entries({ entry_date: entry.entry_date, title: entry.title, timezone: zone, created_at: entry.created_at, updated_at: entry.updated_at }).map(([key, value]) => `${key}: ${JSON.stringify(value)}`), '---', '', entry.content].join('\n')
}
export function parseJournalDocument(text: string, date: string, revision: string): { entry: Journal; timezone: string } {
  const match = /^\uFEFF?---\r?\n([\s\S]*?)\r?\n---\r?\n\r?\n/.exec(text)
  if (!match || match[1]!.length > 8192) return invalid()
  const fields: Record<string, unknown> = {}
  for (const line of match[1]!.split(/\r?\n/)) {
    const pair = /^([a-z_]+): (.+)$/.exec(line)
    if (!pair || Object.hasOwn(fields, pair[1]!)) return invalid()
    try { fields[pair[1]!] = JSON.parse(pair[2]!) } catch { return invalid() }
  }
  const keys = ['focusnest_journal_version', 'entry_date', 'title', 'timezone', 'created_at', 'updated_at']
  if (Object.keys(fields).length !== keys.length || keys.some(key => !Object.hasOwn(fields, key)) || fields.focusnest_journal_version !== 1 || fields.entry_date !== date || typeof fields.timezone !== 'string') return invalid()
  const entry = { id: `local:${date}`, entry_date: date, title: fields.title, content: text.slice(match[0].length), created_at: fields.created_at, updated_at: fields.updated_at, revision } as Journal
  validate(entry, fields.timezone)
  return { entry, timezone: fields.timezone }
}
export function parseJournal(text: string, date: string, revision: string): Journal { return parseJournalDocument(text, date, revision).entry }
