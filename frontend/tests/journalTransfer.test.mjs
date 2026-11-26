import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { File } from 'node:buffer'
import { webcrypto } from 'node:crypto'
import { loadTs } from './helpers/loadTs.mjs'
if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
const transfer = await loadTs(new URL('../src/services/journalTransfer.ts', import.meta.url))
const { serializeJournal } = await loadTs(new URL('../src/services/journalMarkdown.ts', import.meta.url))
const { createLocalJournalRepository } = await loadTs(new URL('../src/services/localJournalRepository.ts', import.meta.url))
const { createTransferProgress } = await loadTs(new URL('../src/services/journalTransferProgress.ts', import.meta.url))
const fixture = JSON.parse(readFileSync(new URL('./fixtures/journalTransferDigest.json', import.meta.url), 'utf8'))
const lock = operation => operation()

function memoryDirectory(name = 'root') {
  const files = new Map(), directories = new Map()
  const handle = {
    kind: 'directory', name, async queryPermission() { return 'granted' },
    async getDirectoryHandle(part, options) {
      if (!directories.has(part)) { if (!options?.create) throw new DOMException('missing', 'NotFoundError'); directories.set(part, memoryDirectory(part)) }
      return directories.get(part).handle
    },
    async *values() { for (const key of directories.keys()) yield { name: key, kind: 'directory' }; for (const key of files.keys()) yield { name: key, kind: 'file' } },
    async removeEntry(part) { files.delete(part) },
    async getFileHandle(part, options) {
      if (!files.has(part)) { if (!options?.create) throw new DOMException('missing', 'NotFoundError'); files.set(part, '') }
      return { async getFile() { return new File([files.get(part)], part) }, async createWritable() { let pending; return { async write(text) { pending = text }, async close() { files.set(part, pending) }, async abort() {} } } }
    },
  }
  return { files, directories, handle }
}
function setup() {
  const directory = memoryDirectory(); let active = true
  const connection = { handle: directory.handle, isCurrent: () => active }
  return { directory, connection, local: createLocalJournalRepository(connection, () => 'UTC', lock), progress: createTransferProgress(connection, 'account-a', lock), invalidate() { active = false } }
}

test('plain Markdown imports preserve bytes/body and require a date rather than assuming today', async () => {
  const file = new File(['\uFEFF# 日记\r\n尾部  \r\n'], 'untitled.md')
  const before = await file.text()
  const item = await transfer.parseImportFile(file, 'UTC')
  assert.equal(item.status, 'needs_date'); assert.equal(item.entry.entry_date, '')
  assert.equal(item.entry.content, '# 日记\r\n尾部  \r\n')
  assert.equal(await file.text(), before)
  assert.equal((await transfer.parseImportFile(new File(['body'], '2026-11-05.md'), 'UTC')).entry.entry_date, '2026-11-05')
})

test('platform format preserves time and timezone; conflicts and invalid encodings are rejected', async () => {
  const text = serializeJournal(fixture.entry, 'Asia/Shanghai')
  const item = await transfer.parseImportFile(new File([text], '2026-11-05.md'), 'UTC')
  assert.equal(item.entry.created_at, fixture.entry.created_at); assert.equal(item.timezone, 'Asia/Shanghai')
  assert.equal(item.entry.content, fixture.entry.content)
  await assert.rejects(() => transfer.parseImportFile(new File([text], '2026-11-04.md'), 'UTC'))
  await assert.rejects(() => transfer.parseImportFile(new File([text.replace('version: 1', 'version: 99')], 'x.md'), 'UTC'))
  for (const file of [new File([new Uint8Array([255, 254])], 'x.md'), new File(['x\0y'], 'x.md'), new File(['x'], 'x.docx'), new File([], 'x.md'), new File(['x'], '2026-02-30.md')]) await assert.rejects(() => transfer.parseImportFile(file, 'UTC'))
})

test('ordinary YAML remains body text even if a later code sample mentions the platform marker', async () => {
  const content = '---\ntags: personal\n---\n\nfocusnest_journal_version: example\n'
  const item = await transfer.parseImportFile(new File([content], '2026-11-05.md'), 'UTC')
  assert.equal(item.preserveMetadata, false); assert.equal(item.entry.content, content)
})

test('duplicate target dates block the batch without writing any file', async () => {
  const s = setup()
  const a = await transfer.parseImportFile(new File(['a'], '2026-11-05.md'), 'UTC')
  const b = await transfer.parseImportFile(new File(['b'], '2026-11-05.md'), 'UTC')
  await transfer.previewTransfers([a, b], s.local)
  assert.equal(a.status, 'conflict'); assert.equal(b.status, 'conflict'); assert.equal(s.directory.directories.size, 0)
})

test('cloud copy preserves all source fields, is repeatable, and never replaces an edited local file', async () => {
  const s = setup(), item = await transfer.cloudTransferItem(fixture.entry, 'UTC')
  await transfer.previewTransfers([item], s.local); assert.equal(item.status, 'ready')
  const first = await transfer.copyAndVerify(item, s.local)
  assert.equal(first.created_at, fixture.entry.created_at); assert.equal(first.updated_at, fixture.entry.updated_at)
  assert.equal((await transfer.copyAndVerify(item, s.local)).revision, first.revision)
  await s.local.save(first.entry_date, { title: 'User edit', content: 'Keep new local work', expected_revision: first.revision })
  await transfer.previewTransfers([item], s.local); assert.equal(item.status, 'conflict')
  await assert.rejects(() => transfer.copyAndVerify(item, s.local))
  assert.equal((await s.local.getDay(first.entry_date)).entry.content, 'Keep new local work')
})

test('matching plain Markdown does not rewrite existing local timestamps', async () => {
  const s = setup(), item = await transfer.parseImportFile(new File(['body'], '2026-11-05.md'), 'UTC')
  const first = await transfer.copyAndVerify(item, s.local)
  item.entry.created_at = '2020-01-01T00:00:00Z'
  assert.equal((await transfer.copyAndVerify(item, s.local)).revision, first.revision)
})

test('platform import checks timezone as well as body and time metadata', async () => {
  const s = setup()
  await s.local.importEntry(fixture.entry, 'UTC')
  const item = await transfer.parseImportFile(new File([serializeJournal(fixture.entry, 'Asia/Shanghai')], '2026-11-05.md'), 'UTC')
  await transfer.previewTransfers([item], s.local)
  assert.equal(item.status, 'conflict')
  await assert.rejects(() => transfer.copyAndVerify(item, s.local))
  assert.equal((await s.local.readDocument(item.entry.entry_date)).timezone, 'UTC')
})

test('progress is account scoped, persists only metadata, and rejects corrupt files without overwriting', async () => {
  const s = setup(), item = await transfer.cloudTransferItem(fixture.entry, 'UTC')
  const entry = await transfer.copyAndVerify(item, s.local)
  const record = { key: item.key + ':' + entry.entry_date, origin: 'cloud', sourceHash: item.sourceHash, sourceRevision: item.entry.revision, targetDate: entry.entry_date, localRevision: entry.revision, verifiedAt: new Date().toISOString(), state: 'verified' }
  await s.progress.save(record)
  assert.deepEqual((await s.progress.read()).records, [record])
  const other = createTransferProgress(s.connection, 'account-b', lock)
  assert.deepEqual((await other.read()).records, [])
  const raw = s.directory.files.get(s.progress.name)
  assert.ok(!raw.includes(fixture.entry.title)); assert.ok(!raw.includes('尾部空格'))
  s.directory.files.set(s.progress.name, 'Keep damaged original')
  await assert.rejects(() => s.progress.save(record))
  assert.equal(s.directory.files.get(s.progress.name), 'Keep damaged original')
})

test('source digest matches a fixed cross-language Unicode and timestamp fixture', async () => {
  assert.equal(await transfer.sourceDigest(fixture.entry), fixture.digest)
})

test('cleanup rechecks local revision before reading cloud and rejects changed source content', async () => {
  const s = setup(), item = await transfer.cloudTransferItem(fixture.entry, 'UTC')
  await transfer.copyAndVerify(item, s.local)
  const payload = await transfer.verifyBeforeCleanup(item, s.local, async () => fixture.entry)
  assert.equal(payload.verified_source_digest, fixture.digest); assert.equal(payload.confirmation, 'DELETE_CLOUD_COPY')
  await assert.rejects(() => transfer.verifyBeforeCleanup(item, s.local, async () => ({ ...fixture.entry, content: 'Changed without revision' })))
  assert.equal((await transfer.verifyBeforeCleanup(item, s.local, async () => null)).missing, true)
  await s.local.save(item.entry.entry_date, { title: '', content: 'Local edit', expected_revision: item.localRevision })
  let reads = 0
  await assert.rejects(() => transfer.verifyBeforeCleanup(item, s.local, async () => { reads++; return fixture.entry }))
  assert.equal(reads, 0)
})

test('invalidated directory cannot continue a copy or persist old account progress', async () => {
  const s = setup(), item = await transfer.cloudTransferItem(fixture.entry, 'UTC')
  s.invalidate()
  await assert.rejects(() => transfer.copyAndVerify(item, s.local))
  await assert.rejects(() => s.progress.read())
  assert.equal(s.directory.files.size, 0); assert.equal(s.directory.directories.size, 0)
})

test('cleanup rejects a local edit made while awaiting the cloud verification', async () => {
  const s = setup(), item = await transfer.cloudTransferItem(fixture.entry, 'UTC')
  await transfer.copyAndVerify(item, s.local)
  await assert.rejects(() => transfer.verifyBeforeCleanup(item, s.local, async () => {
    await s.local.save(item.entry.entry_date, { title: 'New local work', content: 'Changed during cloud read', expected_revision: item.localRevision })
    return fixture.entry
  }))
  assert.equal((await s.local.getDay(item.entry.entry_date)).entry.content, 'Changed during cloud read')
})
