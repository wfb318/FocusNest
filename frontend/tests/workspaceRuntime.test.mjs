import { readFileSync } from 'node:fs'
import { test, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
import { createPinia, setActivePinia } from 'pinia'

const uri = text => `data:text/javascript;base64,${Buffer.from(text).toString('base64')}`
const compile = path => ts.transpile(readFileSync(new URL(path, import.meta.url), 'utf8'), { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 })
const mocks = {
  vue: import.meta.resolve('vue'), pinia: import.meta.resolve('pinia'),
  './auth': uri('export const useAuthStore = () => globalThis.__runtimeTest.auth'),
  './reminders': uri('export const useReminders = () => globalThis.__runtimeTest.reminders'),
  '../api/focus': uri('export const currentFocus = () => globalThis.__runtimeTest.readTimer()'),
  '../api/schedules': uri('export const carryScheduleTemplate = () => globalThis.__runtimeTest.carry(); export const listSchedule = () => globalThis.__runtimeTest.readSchedule(); export const startOccurrence = () => globalThis.__runtimeTest.autoStart()'),
  '../api/client': uri('export const errorMessage = e => e.message'),
  '../utils/scheduleTime': uri(compile('../src/utils/scheduleTime.ts')),
}
const source = compile('../src/stores/workspaceRuntime.ts').replace(/from (['"])([^'"]+)\1/g, (_, _q, name) => `from '${mocks[name]}'`)
const { useWorkspaceRuntime } = await import(uri(source))
const original = { window: globalThis.window, document: globalThis.document, localStorage: globalThis.localStorage, performance: globalThis.performance, now: Date.now, setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval }
let state, store, clock, base, intervals
const iso = stamp => new Date(stamp).toISOString()
function timer(overrides = {}) {
  return { id: 'timer-1', mode: 'countdown', kind: 'focus', status: 'running', title: 'Reading', task_id: null, duration_seconds: 60, elapsed_seconds: 0, started_at: iso(base), server_now: iso(base + clock), window_start: null, window_end: null, occurrence_key: null, ...overrides }
}
function occurrence() {
  return { schedule_id: 'plan-1', key: 'plan-1:2026-11-02', title: 'Study', occurrence_date: '2026-11-02', starts_at: iso(base - 60000), ends_at: iso(base + 60000), timer_enabled: true, remind_start: true, remind_end: true, skipped: false, time_warning: false }
}
async function boot() { store = useWorkspaceRuntime(); store.start(); await store.sync() }
function advance(ms) { clock += ms; for (const interval of intervals.values()) if (interval.delay === 250) interval.fn() }
beforeEach(() => {
  base = Date.parse('2026-11-02T01:00:00Z'); clock = 0; intervals = new Map()
  const storage = new Map(); globalThis.localStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) }
  globalThis.window = Object.assign(new EventTarget(), { innerWidth: 1600 })
  globalThis.document = new EventTarget(); globalThis.performance = { now: () => clock }; Date.now = () => base + clock
  globalThis.setInterval = (fn, delay) => { const id = Symbol(); intervals.set(id, { fn, delay }); return id }
  globalThis.clearInterval = id => intervals.delete(id)
  state = { auth: { user: { id: 'user-1', timezone: 'Asia/Shanghai' } }, timer: null, items: [], alerts: [], autoCalls: 0,
    carryCalls: 0, async carry() { ++state.carryCalls },
    reminders: { configure() {}, notify(id, text) { state.alerts.push({ id, text }) } },
    async readTimer() { return state.timer ? { ...state.timer, server_now: iso(base + clock) } : null },
    async readSchedule() { return { items: state.items, server_now: iso(base + clock) } },
    async autoStart() { ++state.autoCalls; state.timer = timer({ mode: 'scheduled', duration_seconds: null, occurrence_key: state.items[0].key, window_start: state.items[0].starts_at, window_end: state.items[0].ends_at }); return state.timer },
  }
  globalThis.__runtimeTest = state; setActivePinia(createPinia())
})
afterEach(() => {
  store?.stop(); store = undefined
  for (const name of ['window', 'document', 'localStorage', 'performance', 'setInterval', 'clearInterval']) { if (original[name] === undefined) delete globalThis[name]; else globalThis[name] = original[name] }
  Date.now = original.now; delete globalThis.__runtimeTest
})
test('global timer advances between syncs and a paused timer stays still', async () => {
  state.timer = timer(); await boot(); advance(10000)
  assert.equal(store.displaySeconds, 50)
  store.apply(timer({ status: 'paused', elapsed_seconds: 10 })); advance(10000)
  assert.equal(store.displaySeconds, 50)
})
test('the workspace prepares the schedule once per local week before reading it', async () => {
  state.readSchedule = async () => {
    assert.ok(state.carryCalls > 0)
    return { items: [], server_now: iso(base + clock) }
  }
  await boot()
  await store.sync()
  assert.equal(state.carryCalls, 1)
  advance(7 * 86400000)
  await store.sync()
  assert.equal(state.carryCalls, 2)
})
test('fixed timer waits then emits start and end boundaries outside the focus view', async () => {
  state.timer = timer({ mode: 'scheduled', status: 'scheduled', duration_seconds: null, started_at: iso(base + 10000), window_start: iso(base + 10000), window_end: iso(base + 70000) })
  await boot(); assert.equal(store.waiting, true); assert.equal(store.displaySeconds, 10)
  advance(11000); assert.equal(store.waiting, false); assert.equal(store.displaySeconds, 59)
  for (let i = 0; i < 3; ++i) { await store.sync(); advance(20000) }
  assert.equal(store.displaySeconds, 0)
  assert.deepEqual(state.alerts.map(item => item.id), ['timer:timer-1:start', 'timer:timer-1:end'])
})
test('automatic schedule start happens once and a current timer is never overwritten', async () => {
  state.items = [occurrence()]; await boot(); await store.sync(); await store.sync()
  assert.equal(state.autoCalls, 1); assert.equal(store.current.occurrence_key, 'plan-1:2026-11-02')
  store.stop(); state.autoCalls = 0; state.timer = timer({ id: 'manual' }); store.start(); await store.sync()
  assert.equal(state.autoCalls, 0); assert.equal(store.current.id, 'manual'); assert.match(store.conflict, /已有活动计时/)
})
test('stale responses after logout cannot restore private runtime state', async () => {
  let resolveTimer, timerStarted
  const started = new Promise(resolve => { timerStarted = resolve })
  state.readTimer = () => new Promise(resolve => { resolveTimer = resolve; timerStarted() })
  store = useWorkspaceRuntime(); store.start(); const pending = store.sync(); await started; store.stop(); resolveTimer(timer()); await pending
  assert.equal(store.current, null); assert.deepEqual(store.occurrences, []); assert.equal(store.ready, false)
})
test('polling does not race a manual timer mutation', async () => {
  await boot(); let resolveAction
  const action = store.mutate(() => new Promise(resolve => { resolveAction = resolve }))
  await store.sync(); resolveAction(timer({ id: 'new-manual' })); await action
  assert.equal(store.current.id, 'new-manual'); assert.equal(store.mutating, false)
})
test('next schedule follows actual instants across saved timezones', async () => {
  state.items = [
    { ...occurrence(), key: 'later', starts_at: '2026-11-02T08:00:00+01:00', ends_at: '2026-11-02T09:00:00+01:00' },
    { ...occurrence(), key: 'earlier', starts_at: '2026-11-02T15:30:00+10:00', ends_at: '2026-11-02T16:30:00+10:00' },
  ]
  await boot(); assert.equal(store.nextSchedule.key, 'earlier')
})
test('manual finish triggers an end event but cancel stays quiet', async () => {
  state.timer = timer({ mode: 'stopwatch', duration_seconds: null }); await boot()
  await store.mutate(async () => timer({ status: 'completed' }))
  assert.equal(state.alerts[0].id, 'timer:timer-1:end')
  store.apply(timer({ id: 'cancel-me' }))
  await store.mutate(async () => timer({ id: 'cancel-me', status: 'cancelled' }))
  assert.equal(state.alerts.length, 1)
})
test('finishing an expired linked timer shares its schedule end event key', async () => {
  state.timer = timer({ mode: 'scheduled', occurrence_key: 'plan:2026-11-02', window_end: iso(base + 60000), window_start: iso(base) }); await boot()
  await store.mutate(async () => ({ ...state.timer, status: 'completed', ended_at: iso(base + 60000) }))
  assert.equal(state.alerts[0].id, 'schedule:plan:2026-11-02:end')
})
