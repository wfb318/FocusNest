import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

const source = ts.transpile(readFileSync(new URL('../src/services/journalStorage.ts', import.meta.url), 'utf8'), { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 })
const { createJournalStorage, directoryCapability } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const input = { title: 'Private title', content: 'Private body', expected_revision: null }
const query = { page: 1, page_size: 10 }
function transport() {
  const calls = []
  const api = Object.fromEntries(['getDay', 'today', 'list', 'save', 'delete'].map(method => [method, async (...args) => { calls.push([method, ...args]); return { method } }]))
  return { calls, api }
}
async function rejectsAll(storage, code) {
  for (const operation of [() => storage.getDay('2026-11-05'), () => storage.today(), () => storage.list(query), () => storage.save('2026-11-05', input), () => storage.delete('2026-11-05', 'revision')]) {
    await assert.rejects(operation, error => error.code === code)
  }
}

test('unbound local source never reads or uploads through cloud, even with legacy permission', async () => {
  const { api, calls } = transport()
  const local = createJournalStorage('local', api, { purpose: 'legacy-migration', isCurrent: () => true })
  await rejectsAll(local, 'LOCAL_DIRECTORY_UNBOUND')
  assert.equal(local.availability, 'unbound')
  assert.equal(local.writable, false)
  assert.deepEqual(calls, [])
})

test('encrypted source requires explicit access and cannot fall back to plaintext cloud', async () => {
  const { api, calls } = transport()
  await rejectsAll(createJournalStorage('cloud_encrypted', api), 'CLOUD_ENCRYPTION_UNAVAILABLE')
  assert.deepEqual(calls, [])
})

test('explicit encrypted storage writes only while its account context remains current', async () => {
  const { api, calls } = transport()
  let current = true
  const encrypted = createJournalStorage('cloud_encrypted', api, {
    purpose: 'encrypted-journal', isCurrent: () => current,
  })
  await encrypted.save('2026-11-08', input)
  current = false
  await assert.rejects(() => encrypted.save('2026-11-09', input), { code: 'SESSION_CHANGED' })
  assert.deepEqual(calls, [['save', '2026-11-08', input]])
})

test('cloud requires both explicit legacy access and an account lifetime guard', async () => {
  const { api, calls } = transport()
  await rejectsAll(createJournalStorage('cloud', api), 'LEGACY_ACCESS_REQUIRED')
  await rejectsAll(createJournalStorage('cloud', api, { purpose: 'legacy-migration' }), 'LEGACY_ACCESS_REQUIRED')
  assert.deepEqual(calls, [])
})

test('explicit legacy source reads through adapter and rejects all mutations', async () => {
  const { api, calls } = transport()
  const legacy = createJournalStorage('cloud', api, { purpose: 'legacy-migration', isCurrent: () => true })
  await legacy.getDay('2026-11-05'); await legacy.today(); await legacy.list(query)
  await assert.rejects(() => legacy.save('2026-11-05', input), { code: 'LEGACY_READ_ONLY' })
  await assert.rejects(() => legacy.delete('2026-11-05', 'revision'), { code: 'LEGACY_READ_ONLY' })
  assert.deepEqual(calls, [['getDay', '2026-11-05'], ['today'], ['list', query]])
})

test('legacy network failures propagate without retrying or switching sources', async () => {
  const { api, calls } = transport()
  const failure = new Error('offline')
  api.list = async () => { calls.push('list'); throw failure }
  const legacy = createJournalStorage('cloud', api, { purpose: 'legacy-migration', isCurrent: () => true })
  await assert.rejects(() => legacy.list(query), error => error === failure)
  assert.deepEqual(calls, ['list'])
})

test('account change blocks new requests and discards late successful private data', async () => {
  const { api, calls } = transport()
  let current = true, resolve
  api.getDay = () => new Promise(done => { resolve = done })
  const legacy = createJournalStorage('cloud', api, { purpose: 'legacy-migration', isCurrent: () => current })
  const pending = legacy.getDay('2026-11-05')
  current = false
  resolve({ entry_date: '2026-11-05', entry: input })
  await assert.rejects(() => pending, { code: 'SESSION_CHANGED' })
  await assert.rejects(() => legacy.list(query), { code: 'SESSION_CHANGED' })
  assert.deepEqual(calls, [])
})

test('late private errors are discarded after closing the account context', async () => {
  const { api } = transport()
  let current = true, reject
  api.list = () => new Promise((_, fail) => { reject = fail })
  const legacy = createJournalStorage('cloud', api, { purpose: 'legacy-migration', isCurrent: () => current })
  const pending = legacy.list(query)
  current = false; reject(new Error('Old account private error'))
  await assert.rejects(() => pending, error => error.code === 'SESSION_CHANGED' && !error.message.includes('private'))
})

test('directory capability checks support without calling the directory picker', () => {
  let calls = 0
  const showDirectoryPicker = () => { calls++ }
  assert.equal(directoryCapability({ isSecureContext: true, showDirectoryPicker }), 'supported')
  assert.equal(directoryCapability({ isSecureContext: false, showDirectoryPicker }), 'insecure')
  assert.equal(directoryCapability({ isSecureContext: true }), 'unsupported')
  assert.equal(calls, 0)
})

test('dashboard client explicitly excludes legacy journal metadata', async () => {
  const requests = []
  const client = { get: async (...args) => { requests.push(args); return { data: { data: { task_total: 0 } } } } }
  const stub = `export const apiClient = globalThis.__journalTestClient`
  const stubUrl = `data:text/javascript;base64,${Buffer.from(stub).toString('base64')}`
  const compiled = ts.transpile(readFileSync(new URL('../src/api/dashboard.ts', import.meta.url), 'utf8'), { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }).replace("'./client'", JSON.stringify(stubUrl))
  globalThis.__journalTestClient = client
  try {
    const { getDashboard } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
    await getDashboard()
    assert.deepEqual(requests, [['/dashboard', { params: { include_journal: false } }]])
  } finally { delete globalThis.__journalTestClient }
})
