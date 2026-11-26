import assert from 'node:assert/strict'
import test from 'node:test'
import { loadTs } from './helpers/loadTs.mjs'

const { createPresenceReporter } = await loadTs(new URL('../src/utils/presence.ts', import.meta.url))

test('presence is throttled, ignores hidden accounts and stops after unmount', async () => {
  let visible = false, time = 0, sent = 0
  const reporter = createPresenceReporter({ active: () => visible, send: async () => { sent++ }, now: () => time })
  await reporter.tick()
  assert.equal(sent, 0)
  visible = true
  await reporter.tick()
  await reporter.tick()
  assert.equal(sent, 1)
  time = 60_000
  await reporter.tick()
  assert.equal(sent, 2)
  visible = false; time = 120_000
  await reporter.tick()
  assert.equal(sent, 2)
  visible = true
  await reporter.tick()
  assert.equal(sent, 3)
  reporter.stop(); time += 60_000
  await reporter.tick()
  assert.equal(sent, 3)
})

test('only one heartbeat is in flight, and stopping prevents future attempts', async () => {
  let finish, time = 0, sent = 0
  const reporter = createPresenceReporter({ active: () => true, now: () => time, send: () => { sent++; return new Promise(resolve => { finish = resolve }) } })
  const pending = reporter.tick()
  time = 120_000
  await reporter.tick()
  assert.equal(sent, 1)
  reporter.stop(); finish(); await pending
  await reporter.tick()
  assert.equal(sent, 1)
})

test('failures stay contained and a later online heartbeat can recover without contents', async () => {
  let time = 0, sent = 0
  const reporter = createPresenceReporter({ active: () => true, now: () => time, send: async (...args) => { assert.deepEqual(args, []); sent++; if (sent === 1) throw new Error('offline') } })
  await reporter.tick()
  await reporter.tick()
  assert.equal(sent, 1)
  time = 60_000
  await reporter.tick()
  assert.equal(sent, 2)
})
