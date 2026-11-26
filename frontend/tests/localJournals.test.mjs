import { test } from 'node:test'
import assert from 'node:assert/strict'
import { File } from 'node:buffer'
import { webcrypto } from 'node:crypto'
import { mkdtemp, stat, readdir, readFile, writeFile, mkdir, rename, unlink, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve, sep } from 'node:path'
import { loadTs } from './helpers/loadTs.mjs'
if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
const { serializeJournal, parseJournal, validJournalDate } = await loadTs(new URL('../src/services/journalMarkdown.ts', import.meta.url))
const { createLocalJournalRepository } = await loadTs(new URL('../src/services/localJournalRepository.ts', import.meta.url))
const lock = operation => operation()
test('logout guard preserves a newer editor guard when an old editor unmounts', async () => {
  const { registerJournalDraftGuard, confirmJournalLeave } = await loadTs(new URL('../src/services/journalDraftGuard.ts', import.meta.url))
  const disposeOld = registerJournalDraftGuard(async () => true)
  const disposeNew = registerJournalDraftGuard(async () => false)
  disposeOld(); assert.equal(await confirmJournalLeave(), false)
  disposeNew(); assert.equal(await confirmJournalLeave(), true)
})
const entry = { id: 'local:2026-11-05', entry_date: '2026-11-05', title: '标题："测试" 😀', content: '    code\nline  \n\n---\n', created_at: '2026-11-05T00:00:00Z', updated_at: '2026-11-05T00:00:00Z', revision: 'revision' }
test('Markdown v1 roundtrip preserves quotes, Unicode, body indentation and trailing newlines', () => {
  const text = serializeJournal(entry, 'Asia/Shanghai')
  assert.deepEqual(parseJournal(text, entry.entry_date, 'revision'), entry)
  assert.equal(parseJournal('\uFEFF' + text.replaceAll('\n', '\r\n'), entry.entry_date, 'revision').content, entry.content.replaceAll('\n', '\r\n'))
})
test('invalid dates, conflicting metadata, unsafe YAML and invalid content fail closed', () => {
  for (const day of ['2026-02-30', '../2026-11-05', '0001-01-01', '2026-13-01']) assert.throws(() => validJournalDate(day))
  const text = serializeJournal(entry, 'UTC')
  for (const value of [text.replace('version: 1', 'version: 2'), text.replace('title: ', 'title: !!js/function '), text.replace('timezone: "UTC"', 'timezone: "Invalid/Zone"')]) assert.throws(() => parseJournal(value, entry.entry_date, 'r'))
  assert.throws(() => parseJournal(text, '2026-11-04', 'r'))
  assert.throws(() => serializeJournal({ ...entry, content: ' \n ' }, 'UTC'))
  assert.throws(() => serializeJournal({ ...entry, title: '😀'.repeat(201) }, 'UTC'))
  assert.doesNotThrow(() => serializeJournal({ ...entry, title: '😀'.repeat(200) }, 'UTC'))
})

// Real disk adapter; the repository still uses its normal permissions/version checks.
function diskDirectory(path, permission = () => 'granted') {
  return {
    kind: 'directory', name: path.split(/[\\/]/).at(-1),
    async queryPermission() { return permission() },
    async getDirectoryHandle(name, options) {
      const target = join(path, name)
      try { await stat(target) } catch (error) { if (error.code !== 'ENOENT') throw error; if (!options?.create) throw new DOMException('Missing', 'NotFoundError'); await mkdir(target) }
      return diskDirectory(target, permission)
    },
    async *values() { for (const item of await readdir(path, { withFileTypes: true })) yield { name: item.name, kind: item.isDirectory() ? 'directory' : 'file' } },
    async removeEntry(name) { await unlink(join(path, name)) },
    async getFileHandle(name, options) {
      const target = join(path, name)
      try { await stat(target) } catch (error) { if (error.code !== 'ENOENT') throw error; if (!options?.create) throw new DOMException('Missing', 'NotFoundError'); await writeFile(target, '', { flag: 'wx' }) }
      return {
        async getFile() { return new File([await readFile(target)], name) },
        async createWritable() { let draft; return { async write(value) { draft = value }, async close() { await writeFile(target, draft) }, async abort() {} } },
      }
    },
  }
}
async function fixture(run) {
  const root = await mkdtemp(join(tmpdir(), 'FocusNest-journal-'))
  let active = true, permission = 'granted'
  const connection = { handle: diskDirectory(root, () => permission), isCurrent: () => active }
  const repository = createLocalJournalRepository(connection, () => 'Asia/Shanghai', lock)
  try { await run({ root, repository, connection, revoke() { permission = 'denied' }, switchAccount() { active = false } }) }
  finally {
    if (!resolve(root).startsWith(resolve(tmpdir()) + sep + 'FocusNest-journal-')) throw new Error('Unsafe test cleanup target')
    await rm(root, { recursive: true, force: true })
  }
}
test('real disk journal create, reopen, update, list, local search and version-checked delete', () => fixture(async ({ root, repository }) => {
  const day = '2026-11-05'
  assert.equal((await repository.getDay(day)).entry, null)
  const saved = await repository.save(day, { title: '  私人标题  ', content: entry.content, expected_revision: null })
  assert.equal(saved.title, '私人标题'); assert.equal(saved.revision.length, 64)
  assert.equal((await readFile(join(root, '2026', '11', day + '.md'), 'utf8')).includes('私人标题'), true)
  assert.deepEqual((await repository.getDay(day)).entry, saved)
  const updated = await repository.save(day, { title: '新标题', content: '100%_literal', expected_revision: saved.revision })
  assert.equal(updated.created_at, saved.created_at); assert.notEqual(updated.revision, saved.revision)
  assert.equal((await repository.list({ page: 1, page_size: 10, q: '%_' })).total, 1)
  assert.equal('content' in (await repository.list({ page: 1, page_size: 10 })).items[0], false)
  await assert.rejects(() => repository.delete(day, saved.revision), { code: 'FILE_CONFLICT' })
  await repository.delete(day, updated.revision)
  assert.equal((await repository.getDay(day)).entry, null)
}))
test('outside edits and malformed files are never silently overwritten', () => fixture(async ({ root, repository }) => {
  const saved = await repository.save(entry.entry_date, { title: entry.title, content: entry.content, expected_revision: null })
  const path = join(root, '2026', '11', entry.entry_date + '.md')
  await writeFile(path, serializeJournal({ ...entry, content: '外部修改' }, 'UTC'))
  await assert.rejects(() => repository.save(entry.entry_date, { title: 'new', content: 'draft', expected_revision: saved.revision }), { code: 'FILE_CONFLICT' })
  await writeFile(path, 'Unrecognized original markdown')
  await assert.rejects(() => repository.save(entry.entry_date, { title: 'new', content: 'draft', expected_revision: null }), { code: 'INVALID_FILE' })
  assert.equal(await readFile(path, 'utf8'), 'Unrecognized original markdown')
}))
test('moving the bound directory does not overwrite or recreate the saved journal', () => fixture(async ({ root, repository }) => {
  const day = entry.entry_date
  const saved = await repository.save(day, { title: entry.title, content: entry.content, expected_revision: null })
  const moved = root + '-moved'
  const relative = join('2026', '11', day + '.md')
  const original = await readFile(join(root, relative))
  await rename(root, moved)
  try {
    await assert.rejects(() => repository.save(day, { title: 'new', content: 'draft', expected_revision: saved.revision }), { code: 'FILE_CONFLICT' })
    await assert.rejects(() => stat(root), { code: 'ENOENT' })
    assert.deepEqual(await readFile(join(moved, relative)), original)
  } finally { await rename(moved, root) }
}))
test('pagination/date range remain local; unrelated documents are ignored', () => fixture(async ({ root, repository }) => {
  await writeFile(join(root, 'private-unrelated.md'), 'Not a journal')
  for (const date of ['2026-10-31', '2026-11-01', '2026-11-05']) await repository.save(date, { title: date, content: 'body', expected_revision: null })
  const one = await repository.list({ page: 1, page_size: 1, start_date: '2026-11-01' })
  assert.equal(one.total, 2); assert.equal(one.items[0].entry_date, '2026-11-05')
  assert.equal((await repository.list({ page: 2, page_size: 1, start_date: '2026-11-01' })).items[0].entry_date, '2026-11-01')
}))
test('revoked permission and changed account reject reads and writes', () => fixture(async ({ repository, revoke, switchAccount }) => {
  revoke(); await assert.rejects(() => repository.getDay('2026-11-05'), { code: 'PERMISSION_REQUIRED' })
  switchAccount(); await assert.rejects(() => repository.list({ page: 1, page_size: 10 }), { code: 'SESSION_CHANGED' })
  await assert.rejects(() => repository.save('2026-11-05', { title: '', content: 'secret', expected_revision: null }), { code: 'SESSION_CHANGED' })
}))
test('today follows the account timezone rather than server or browser timezone', () => fixture(async ({ connection }) => {
  const originalNow = Date.now
  Date.now = () => Date.parse('2026-11-05T00:30:00Z')
  try {
    const western = createLocalJournalRepository(connection, () => 'America/Los_Angeles', lock)
    assert.equal((await western.today()).entry_date, '2026-11-04')
    const eastern = createLocalJournalRepository(connection, () => 'Asia/Shanghai', lock)
    assert.equal((await eastern.today()).entry_date, '2026-11-05')
  } finally { Date.now = originalNow }
}))
