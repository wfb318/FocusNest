import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
const source = readFileSync(new URL('../src/utils/scheduleTime.ts', import.meta.url), 'utf8')
const js = ts.transpile(source, { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 })
const { addDays, dateInZone, weekStart, minuteLabel, secondsLabel, zonedInstant } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
test('week boundaries and day arithmetic survive month/year changes', () => {
  assert.equal(weekStart('2026-11-08'), '2026-11-02')
  assert.equal(weekStart('2026-11-02'), '2026-11-02')
  assert.equal(addDays('2026-12-31', 1), '2027-01-01')
  assert.equal(dateInZone(Date.parse('2026-11-02T17:00Z'), 'Asia/Shanghai'), '2026-11-03')
})
test('fixed-time inputs use profile timezone and reject nonexistent DST time', () => {
  assert.equal(zonedInstant('2026-11-02T09:00', 'Asia/Shanghai'), '2026-11-02T01:00:00.000Z')
  assert.equal(zonedInstant('2026-11-01T01:30', 'America/New_York'), '2026-11-01T05:30:00.000Z')
  assert.throws(() => zonedInstant('2027-03-14T02:30', 'America/New_York'))
  assert.throws(() => zonedInstant('2026-02-30T10:00', 'UTC'))
})
test('countdown stays nonnegative and supports midnight', () => {
  assert.equal(minuteLabel(1440), '24:00')
  assert.equal(secondsLabel(-3), '00:00:00')
  assert.equal(secondsLabel(60.1), '00:01:01')
})
