import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

const source = ts.transpile(readFileSync(new URL('../src/stores/reminders.ts', import.meta.url), 'utf8'), { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }).replace("from 'vue'", `from '${import.meta.resolve('vue')}'`)
const { useReminders } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
test('reminders deduplicate persisted boundaries and isolate accounts', async () => {
  const previous = globalThis.localStorage
  const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} })
  const data = new Map(); globalThis.localStorage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) }
  try {
    const reminders = useReminders(); reminders.configure('alice')
    await reminders.notify('start:one', 'First'); await reminders.notify('start:one', 'Duplicate')
    assert.equal(reminders.messages.value.length, 1)
    reminders.configure('alice'); await reminders.notify('start:one', 'After reload')
    assert.equal(reminders.messages.value.length, 0)
    reminders.configure('bob'); await reminders.notify('start:one', 'Another account')
    assert.equal(reminders.messages.value[0].text, 'Another account')
    data.set('focusnest-reminders:bob:seen', 'null')
    await reminders.notify('end:two', 'Invalid ledger recovers')
    assert.equal(reminders.messages.value.length, 2)
  } finally {
    if (previous === undefined) delete globalThis.localStorage; else globalThis.localStorage = previous
    if (navigatorDescriptor) Object.defineProperty(globalThis, 'navigator', navigatorDescriptor); else delete globalThis.navigator
  }
})
test('end chime is enabled by default, deduplicated, and respects mute', async () => {
  const savedStorage = globalThis.localStorage, savedAudio = globalThis.AudioContext
  const nav = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} })
  const values = new Map(), tones = []
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
  globalThis.AudioContext = class {
    state = 'suspended'; currentTime = 10; destination = {}
    async resume() { this.state = 'running' }
    createOscillator() { const node = { frequency: {}, connect() {}, disconnect() {}, start(at) { tones.push({ at, frequency: node.frequency.value }) }, stop() {} }; return node }
    createGain() { return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {}, disconnect() {} } }
  }
  try {
    const r = useReminders(); r.configure('sound-check')
    assert.equal(r.preferences.value.endSound, true)
    // A tab unable to play must not consume the sound event.
    await r.notify('timer:one:end', 'Ended')
    assert.equal(tones.length, 0)
    await r.testEndSound(); assert.equal(r.audioReady.value, true); assert.equal(tones.length, 3)
    tones.length = 0
    await r.notify('timer:one:end', 'Ended'); await r.notify('timer:one:end', 'Duplicate')
    assert.deepEqual(tones.map(tone => tone.frequency), [660, 830, 990])
    r.preferences.value.endSound = false; r.save(); r.configure('sound-check')
    assert.equal(r.preferences.value.endSound, false)
    await r.notify('timer:two:end', 'Muted')
    assert.equal(tones.length, 3)
    assert.equal(r.messages.value.length, 1)
  } finally {
    if (savedStorage === undefined) delete globalThis.localStorage; else globalThis.localStorage = savedStorage
    if (savedAudio === undefined) delete globalThis.AudioContext; else globalThis.AudioContext = savedAudio
    if (nav) Object.defineProperty(globalThis, 'navigator', nav); else delete globalThis.navigator
  }
})
