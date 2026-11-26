import { readFileSync } from 'node:fs'
import { beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

const uri = text => `data:text/javascript;base64,${Buffer.from(text).toString('base64')}`
const compile = text => ts.transpile(text, { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 })
const state = {
  auth: { user: { timezone: 'Asia/Shanghai' } },
  runtime: { now: Date.parse('2026-11-02T00:00Z'), async prepareSchedules() {}, async sync() {} },
  requests: [], failure: false,
  async createSchedule(value) { this.requests.push(['create', value]) },
  async removeSchedule(id, value) {
    if (this.failure) throw new Error('Schedule changed; reload')
    this.requests.push(['remove', id, value])
  },
  async listSchedule() { return { items: [], template_id: null } },
  async listTasks() { return { items: [], total: 0 } },
}
globalThis.__scheduleOptionsTest = state
const apiNames = ['applyScheduleTemplate', 'createSchedule', 'editSchedule', 'getScheduleTemplateReview', 'keepScheduleWeek', 'listSchedule', 'listScheduleTemplates', 'removeSchedule', 'saveScheduleTemplate']
const mocks = {
  vue: uri(`export { computed, reactive, ref } from ${JSON.stringify(import.meta.resolve('vue'))}; export const onMounted = () => {}; export const watch = () => {};`),
  'vue-router': uri('export const useRoute = () => ({ query: {} })'),
  '../stores/auth': uri('export const useAuthStore = () => globalThis.__scheduleOptionsTest.auth'),
  '../stores/workspaceRuntime': uri('export const useWorkspaceRuntime = () => globalThis.__scheduleOptionsTest.runtime'),
  '../api/schedules': uri(apiNames.map(name => `export const ${name} = (...args) => globalThis.__scheduleOptionsTest.${name}(...args)`).join(';')),
  '../api/tasks': uri('export const listTasks = (...args) => globalThis.__scheduleOptionsTest.listTasks(...args)'),
  '../api/client': uri('export const errorMessage = e => e.message'),
  '../utils/scheduleTime': uri(compile(readFileSync(new URL('../src/utils/scheduleTime.ts', import.meta.url), 'utf8'))),
}
const component = readFileSync(new URL('../src/views/ScheduleView.vue', import.meta.url), 'utf8')
const script = component.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const source = compile(script + '\nexport { form, week, selected, removalScope, notice, formError, open, save, askRemove, remove };')
  .replace(/from (['"])([^'"]+)\1/g, (_, _q, name) => `from '${mocks[name]}'`)
const view = await import(uri(source))
const occurrence = (repeats = true) => ({
  schedule_id: 'plan-1', occurrence_date: '2026-11-04', weekday: 2, revision: 3,
  title: 'Study', notes: '', start_minute: 540, end_minute: 600, timezone: 'Asia/Shanghai',
  task_id: null, timer_enabled: false, remind_start: true, remind_end: true, repeats,
})
beforeEach(() => { state.requests = []; state.failure = false; view.week.value = '2026-11-02'; view.notice.value = ''; view.open(undefined, '2026-11-04') })

test('temporary creation sends false and the exact selected date', async () => {
  view.form.title = 'Appointment'
  await view.save()
  const [action, payload] = state.requests[0]
  assert.equal(action, 'create')
  assert.equal(payload.repeat_weekly, false)
  assert.equal(payload.effective_from, '2026-11-04')
  assert.equal(payload.weekday, 2)
  assert.equal(payload.timezone, 'Asia/Shanghai')
})

test('weekly creation sends true and the next new form resets to temporary', async () => {
  view.form.title = 'Weekly study'; view.form.repeat_weekly = true
  await view.save()
  assert.equal(state.requests[0][1].repeat_weekly, true)
  view.open(undefined, '2026-11-05')
  assert.equal(view.form.repeat_weekly, false)
})

test('permanent removal uses future scope and the selected date/revision', async () => {
  view.askRemove(occurrence()); view.removalScope.value = 'future'
  await view.remove()
  assert.deepEqual(state.requests[0], ['remove', 'plan-1', { scope: 'future', occurrence_date: '2026-11-04', revision: 3 }])
  assert.match(view.notice.value, /永久/)
})

test('each removal dialog starts with single occurrence selected', async () => {
  view.askRemove(occurrence()); view.removalScope.value = 'future'
  view.askRemove(occurrence())
  assert.equal(view.removalScope.value, 'single')
  await view.remove()
  assert.equal(state.requests[0][2].scope, 'single')
})

test('one-time schedules never send an invalid future removal', async () => {
  view.askRemove(occurrence(false)); view.removalScope.value = 'future'
  await view.remove()
  assert.equal(state.requests[0][2].scope, 'single')
})

test('failed removal retains the error without reporting success', async () => {
  view.askRemove(occurrence()); state.failure = true
  await view.remove()
  assert.equal(state.requests.length, 0)
  assert.equal(view.formError.value, 'Schedule changed; reload')
  assert.equal(view.notice.value, '')
})
