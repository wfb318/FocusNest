import assert from 'node:assert/strict'
import test from 'node:test'
import { loadTs } from './helpers/loadTs.mjs'

const { statisticsRange } = await loadTs(new URL('../src/utils/statistics.ts', import.meta.url))

test('week presets keep Sunday in its current week across a year boundary', () => {
  assert.deepEqual(statisticsRange('week', '2027-01-03'), {
    start_date: '2026-12-28', end_date: '2027-01-03',
  })
  assert.deepEqual(statisticsRange('week', '2027-01-04'), {
    start_date: '2027-01-04', end_date: '2027-01-10',
  })
})

test('month presets cover leap days and roll December into the next year', () => {
  assert.deepEqual(statisticsRange('month', '2024-02-15'), {
    start_date: '2024-02-01', end_date: '2024-02-29',
  })
  assert.deepEqual(statisticsRange('month', '2026-12-31'), {
    start_date: '2026-12-01', end_date: '2026-12-31',
  })
})
