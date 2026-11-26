import { readFileSync } from 'node:fs'
import { File } from 'node:buffer'
import { webcrypto } from 'node:crypto'
import { mkdtemp, readFile, writeFile, unlink, rmdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
const compiled = ts.transpile(readFileSync(new URL('../src/services/localJournalStorage.ts', import.meta.url), 'utf8'), { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 })
const { readLocalFile, writeLocalFile, createDirectoryController } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
const lock = operation => operation()
const current = () => true
const deferred = () => { let resolve, reject; const promise = new Promise((done, fail) => { resolve = done; reject = fail }); return { promise, resolve, reject } }

function directory(name = 'A folder') {
  const files = new Map(), calls = [], value = { permission: 'granted', onWrite: null, failClose: false, aborted: 0 }
  const handle = {
    kind: 'directory', name,
    async queryPermission() { calls.push('query'); return value.permission },
    async requestPermission() { calls.push('request'); value.permission = 'granted'; return value.permission },
    async getFileHandle(filename, options) {
      calls.push(['file', filename, options?.create === true])
      if (!files.has(filename)) {
        if (!options?.create) throw new DOMException('Not found', 'NotFoundError')
        files.set(filename, '')
      }
      return {
        async getFile() { return new File([files.get(filename)], filename) },
        async createWritable() {
          let staged
          return {
            async write(text) { staged = text; if (value.onWrite) await value.onWrite(filename) },
            async close() { if (value.failClose) throw new Error('Private path / forbidden'); files.set(filename, staged) },
            async abort() { value.aborted++ },
          }
        },
      }
    },
  }
  return { handle, files, calls, value }
}

function fixture(selected = directory()) {
  const saved = new Map(), signalHistory = []
  let state, pick = async () => selected.handle
  const bindings = {
    async load(id, signal) { signalHistory.push(signal); return saved.get(id) },
    async save(id, handle, signal) { if (signal.aborted) throw new Error('stale'); saved.set(id, handle) },
    async remove(id, signal) { if (signal.aborted) throw new Error('stale'); saved.delete(id) },
  }
  const controller = createDirectoryController({ bindings, pick: () => pick(), lock }, next => { state = next })
  return { controller, selected, saved, bindings, signalHistory, get state() { return state }, pickWith(callback) { pick = callback } }
}

test('single-file primitives create, read back and check versions before overwriting', async () => {
  const d = directory()
  const initial = await writeLocalFile(d.handle, 'test.txt', 'One\n中文', null, current, lock)
  assert.equal(initial.text, 'One\n中文'); assert.equal(initial.revision.length, 64)
  assert.deepEqual(await readLocalFile(d.handle, 'test.txt', current), initial)
  await assert.rejects(() => writeLocalFile(d.handle, 'test.txt', 'Wrong', null, current, lock), { code: 'FILE_CONFLICT' })
  d.files.set('test.txt', 'External edit')
  await assert.rejects(() => writeLocalFile(d.handle, 'test.txt', 'Wrong', initial.revision, current, lock), { code: 'FILE_CONFLICT' })
  assert.equal(d.files.get('test.txt'), 'External edit')
})

test('path traversal and revoked permission never touch a file or request permission automatically', async () => {
  const d = directory()
  for (const name of ['../private.md', 'C:\\private.md', '/private', '..', 'a/b', 'file.']) {
    await assert.rejects(() => writeLocalFile(d.handle, name, 'x', null, current, lock), { code: 'INVALID_FILE' })
  }
  assert.deepEqual(d.calls, [])
  d.value.permission = 'prompt'
  await assert.rejects(() => readLocalFile(d.handle, 'test.txt', current), { code: 'PERMISSION_REQUIRED' })
  assert.deepEqual(d.calls, ['query'])
})

test('external changes during staging abort the writer and preserve external content', async () => {
  const d = directory()
  const original = await writeLocalFile(d.handle, 'test.txt', 'Initial', null, current, lock)
  d.value.onWrite = name => { d.files.set(name, 'External changed while staging') }
  await assert.rejects(() => writeLocalFile(d.handle, 'test.txt', 'Our draft', original.revision, current, lock), { code: 'FILE_CONFLICT' })
  assert.equal(d.value.aborted, 1)
  assert.equal(d.files.get('test.txt'), 'External changed while staging')
})

test('account change during staging aborts before committing', async () => {
  const d = directory(); let active = true
  d.value.onWrite = () => { active = false }
  await assert.rejects(() => writeLocalFile(d.handle, 'test.txt', 'Private draft', null, () => active, lock), { code: 'SESSION_CHANGED' })
  assert.equal(d.files.get('test.txt'), '')
  assert.equal(d.value.aborted, 1)
})

test('deleted files with an old revision are not silently recreated', async () => {
  const d = directory()
  await assert.rejects(() => writeLocalFile(d.handle, 'missing.txt', 'Draft', 'old', current, lock), { code: 'FILE_CONFLICT' })
  assert.equal(d.files.size, 0)
})

test('bindings restore only for their account and never write files or prompt on restoration', async () => {
  const f = fixture()
  await f.controller.configure('alice'); await f.controller.choose()
  assert.equal(f.state.status, 'ready'); assert.equal(f.selected.files.size, 0)
  await f.controller.configure('bob')
  assert.equal(f.state.directoryName, ''); assert.equal(f.state.status, 'unbound')
  assert.equal(f.signalHistory[0].aborted, true)
  await f.controller.configure('alice')
  assert.equal(f.state.directoryName, 'A folder')
  f.selected.value.permission = 'prompt'
  await f.controller.configure('alice', true)
  assert.equal(f.state.status, 'permission_required')
  assert.ok(!f.selected.calls.includes('request'))
  await f.controller.permission(true)
  assert.equal(f.state.status, 'ready'); assert.ok(f.selected.calls.includes('request'))
})

test('cancelled picker preserves the previous binding', async () => {
  const f = fixture()
  await f.controller.configure('alice'); await f.controller.choose()
  f.pickWith(async () => { throw new DOMException('Cancelled', 'AbortError') })
  await f.controller.choose()
  assert.equal(f.state.directoryName, 'A folder'); assert.equal(f.state.status, 'ready')
  assert.equal(f.state.busy, false); assert.match(f.state.notice, /取消/)
})

test('late picker cannot bind an old account after switch', async () => {
  const f = fixture(), pending = deferred()
  await f.controller.configure('alice'); f.pickWith(() => pending.promise)
  const choosing = f.controller.choose()
  await f.controller.configure('bob')
  pending.resolve(f.selected.handle); await choosing
  assert.equal(f.saved.size, 0); assert.equal(f.state.directoryName, '')
  assert.equal(f.state.status, 'unbound'); assert.equal(f.state.busy, false)
})

test('late directory restoration cannot restore previous account state', async () => {
  const f = fixture(), pending = deferred()
  f.bindings.load = id => id === 'alice' ? pending.promise : Promise.resolve(undefined)
  const restoring = f.controller.configure('alice')
  await f.controller.configure('bob')
  pending.resolve(f.selected.handle); await restoring
  assert.equal(f.state.status, 'unbound'); assert.equal(f.state.directoryName, '')
})

test('failed persistent binding stays session-only with a clear notice', async () => {
  const f = fixture()
  f.bindings.save = async () => { throw new Error('Storage blocked') }
  await f.controller.configure('alice'); await f.controller.choose()
  assert.equal(f.state.status, 'ready'); assert.match(f.state.notice, /本次会话/)
  await f.controller.configure(''); await f.controller.configure('alice')
  assert.equal(f.state.status, 'unbound')
})

test('probe is a separate file and failed writes retain the draft without exposing exception details', async () => {
  const f = fixture()
  await f.controller.configure('alice'); await f.controller.choose(); await f.controller.probe()
  assert.equal(f.state.probeSaved, true); assert.match(f.state.probeName, /^FocusNest-check-[\w-]+\.txt$/)
  const name = f.state.probeName
  f.controller.editProbe('Retain my draft')
  f.selected.value.failClose = true
  await f.controller.probe(true)
  assert.equal(f.state.probeDraft, 'Retain my draft'); assert.equal(f.state.probeSaved, false)
  assert.ok(!f.state.error.includes('/ forbidden'))
  assert.notEqual(f.selected.files.get(name), 'Retain my draft')
})

test('conflicting probe preserves editor input and explicit read permits comparison before retry', async () => {
  const f = fixture()
  await f.controller.configure('alice'); await f.controller.choose(); await f.controller.probe()
  f.controller.editProbe('My pending edit')
  f.selected.files.set(f.state.probeName, 'External version')
  await f.controller.probe(true)
  assert.equal(f.state.probeDraft, 'My pending edit'); assert.match(f.state.error, /修改/)
  assert.equal(await f.controller.reloadProbe(), 'External version')
  assert.equal(f.state.probeDraft, 'My pending edit')
  await f.controller.probe(true)
  assert.equal(f.state.probeSaved, true); assert.equal(f.selected.files.get(f.state.probeName), 'My pending edit')
})

test('unlink removes the browser binding without deleting any files; logout clears drafts', async () => {
  const f = fixture()
  await f.controller.configure('alice'); await f.controller.choose(); await f.controller.probe()
  await f.controller.unbind()
  assert.equal(f.state.status, 'unbound'); assert.equal(f.saved.size, 0); assert.equal(f.selected.files.size, 1)
  assert.equal(f.state.probeDraft, '')
  await f.controller.choose(); await f.controller.probe()
  await f.controller.configure('')
  assert.equal(f.state.status, 'signed_out'); assert.equal(f.state.directoryName, ''); assert.equal(f.state.probeDraft, '')
})

test('queued write checks account lifetime again after obtaining the lock', async () => {
  const d = directory(), pending = deferred(); let active = true
  const queuedLock = async operation => { await pending.promise; return operation() }
  const writing = writeLocalFile(d.handle, 'test.txt', 'Draft', null, () => active, queuedLock)
  active = false; pending.resolve()
  await assert.rejects(() => writing, { code: 'SESSION_CHANGED' })
  assert.equal(d.files.size, 0)
})

test('concurrent same-origin writers serialize and the second sees the changed revision', async () => {
  const d = directory()
  const original = await writeLocalFile(d.handle, 'test.txt', 'Original', null, current, lock)
  let tail = Promise.resolve()
  const serial = operation => { const next = tail.then(operation); tail = next.catch(() => {}); return next }
  const results = await Promise.allSettled([
    writeLocalFile(d.handle, 'test.txt', 'First', original.revision, current, serial),
    writeLocalFile(d.handle, 'test.txt', 'Second', original.revision, current, serial),
  ])
  assert.equal(results[0].status, 'fulfilled'); assert.equal(results[1].reason.code, 'FILE_CONFLICT')
  assert.equal(d.files.get('test.txt'), 'First')
})

test('the file primitives write and read back real disk bytes through a filesystem adapter', async () => {
  const root = await mkdtemp(join(tmpdir(), 'FocusNest-step2-test-'))
  const path = join(root, 'probe.txt')
  const handle = {
    async queryPermission() { return 'granted' },
    async getFileHandle(name, options) {
      assert.equal(name, 'probe.txt')
      try { await readFile(path) }
      catch (error) {
        if (error.code !== 'ENOENT') throw error
        if (!options?.create) throw new DOMException('Missing', 'NotFoundError')
        await writeFile(path, '')
      }
      return {
        async getFile() { return new File([await readFile(path)], name) },
        async createWritable() {
          let pending
          return { async write(text) { pending = text }, async close() { await writeFile(path, pending) }, async abort() {} }
        },
      }
    },
  }
  try {
    const saved = await writeLocalFile(handle, 'probe.txt', '真实磁盘检查\n', null, current, lock)
    assert.equal((await readFile(path, 'utf8')), '真实磁盘检查\n')
    assert.deepEqual(await readLocalFile(handle, 'probe.txt', current), saved)
    await writeFile(path, '外部编辑')
    await assert.rejects(() => writeLocalFile(handle, 'probe.txt', '不能覆盖', saved.revision, current, lock), { code: 'FILE_CONFLICT' })
    assert.equal(await readFile(path, 'utf8'), '外部编辑')
  } finally {
    await unlink(path).catch(error => { if (error.code !== 'ENOENT') throw error })
    await rmdir(root)
  }
})
