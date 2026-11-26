<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { applyScheduleTemplate, createSchedule, editSchedule, getScheduleTemplateReview, keepScheduleWeek, listSchedule, listScheduleTemplates, removeSchedule, saveScheduleTemplate } from '../api/schedules'
import { listTasks } from '../api/tasks'
import { errorMessage } from '../api/client'
import { addDays, dateInZone, minuteLabel, weekStart } from '../utils/scheduleTime'
import type { Occurrence, ScheduleFields, ScheduleTemplate, ScheduleTemplateReview } from '../types/schedule'
import type { Task } from '../types/task'

const auth = useAuthStore(), runtime = useWorkspaceRuntime(), route = useRoute()
const zone = computed(() => auth.user?.timezone || 'Asia/Shanghai')
const week = ref(weekStart(dateInZone(Date.now(), zone.value)))
const days = computed(() => Array.from({ length: 7 }, (_, i) => addDays(week.value, i)))
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const items = ref<Occurrence[]>([]), tasks = ref<Task[]>([]), taskTotal = ref(0), taskPage = ref(1)
const busy = ref(false), loading = ref(false), error = ref(''), formError = ref(''), taskError = ref(''), notice = ref('')
const editor = ref<HTMLDialogElement | null>(null), deleting = ref<HTMLDialogElement | null>(null)
const selected = ref<Occurrence | null>(null)
const form = reactive({ title: '', notes: '', weekday: 0, start: '09:00', end: '10:00', midnight: false, task_id: '', timer_enabled: false, remind_start: true, remind_end: true })
const today = computed(() => dateInZone(runtime.now, zone.value))
const currentWeek = computed(() => weekStart(today.value))
const templates = ref<ScheduleTemplate[]>([]), appliedTemplate = ref<string | null>(null)
const review = ref<ScheduleTemplateReview | null>(null)
const templateDialog = ref<HTMLDialogElement | null>(null)
const templateMode = ref<'save' | 'apply'>('save')
const templateName = ref(''), templateChoice = ref('')
const reviewWeek = computed(() => review.value?.week_start === week.value ? review.value : null)
const suggested = computed(() => templates.value.find(t => t.id === reviewWeek.value?.current_template_id))
const chosenWeekday = computed(() => addDays(week.value, form.weekday))
let loadVersion = 0
const editable = (item: Occurrence) => item.occurrence_date >= dateInZone(runtime.now, item.timezone)
function isCurrent(item: Occurrence) { return !item.skipped && !item.time_warning && Date.parse(item.starts_at!) <= runtime.now && runtime.now < Date.parse(item.ends_at!) }
async function load() {
  const version = ++loadVersion; loading.value = true; error.value = ''
  const start = week.value
  items.value = []
  appliedTemplate.value = null
  try {
    if (start === currentWeek.value) await runtime.prepareSchedules()
    const result = await listSchedule(start, addDays(start, 6))
    if (version === loadVersion) { items.value = result.items; appliedTemplate.value = result.template_id }
  }
  catch (cause) { if (version === loadVersion) error.value = errorMessage(cause) }
  finally { if (version === loadVersion) loading.value = false }
}
function move(amount: number) { week.value = addDays(week.value, amount * 7); void load() }
function thisWeek() { week.value = currentWeek.value; void load() }
async function loadTemplates() {
  try { templates.value = await listScheduleTemplates() }
  catch (cause) { error.value = errorMessage(cause) }
}
async function checkReview(target?: string) {
  try {
    if (new Date(`${today.value}T12:00:00Z`).getUTCDay() !== 0) { review.value = null; return }
    await runtime.prepareSchedules()
    const result = await getScheduleTemplateReview()
    review.value = result
    if (result && target === result.week_start && week.value !== target) { week.value = target; await load() }
  } catch (cause) { error.value = errorMessage(cause) }
}
function openTemplate(mode: 'save' | 'apply') {
  templateMode.value = mode; templateName.value = ''; formError.value = ''
  templateChoice.value = appliedTemplate.value || suggested.value?.id || templates.value[0]?.id || ''
  templateDialog.value?.showModal()
}
async function submitTemplate() {
  if (busy.value) return
  busy.value = true; formError.value = ''
  try {
    if (templateMode.value === 'save') {
      const saved = await saveScheduleTemplate(week.value, templateName.value)
      templates.value = [...templates.value, saved]
      notice.value = `已另存为模板「${saved.name}」。`
    } else {
      await applyScheduleTemplate(templateChoice.value, week.value, appliedTemplate.value)
      notice.value = '模板已应用到这一周。'
      window.dispatchEvent(new Event('focusnest-schedule-review'))
      await load(); await checkReview(); await runtime.sync()
    }
    templateDialog.value?.close()
  } catch (cause) { formError.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function keepWeek() {
  if (busy.value || !reviewWeek.value) return
  busy.value = true; error.value = ''
  try {
    await keepScheduleWeek(week.value)
    review.value = null
    notice.value = '已确认下周日程。'
    window.dispatchEvent(new Event('focusnest-schedule-review'))
    await load(); await runtime.sync()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function loadTasks(more = false) {
  try {
    taskError.value = ''; const page = more ? taskPage.value + 1 : 1
    const result = await listTasks({ page, page_size: 100 })
    tasks.value = more ? [...tasks.value, ...result.items] : result.items; taskTotal.value = result.total; taskPage.value = page
  } catch (cause) { taskError.value = errorMessage(cause) }
}
function open(item?: Occurrence, day?: string) {
  selected.value = item || null; formError.value = ''
  const date = day || (week.value === currentWeek.value ? today.value : week.value)
  Object.assign(form, item ? {
    title: item.title, notes: item.notes, weekday: item.weekday,
    start: minuteLabel(item.start_minute), end: item.end_minute === 1440 ? '23:59' : minuteLabel(item.end_minute), midnight: item.end_minute === 1440,
    task_id: item.task_id || '', timer_enabled: item.timer_enabled, remind_start: item.remind_start, remind_end: item.remind_end,
  } : { title: '', notes: '', weekday: (new Date(`${date}T12:00:00Z`).getUTCDay() + 6) % 7, start: '09:00', end: '10:00', midnight: false, task_id: '', timer_enabled: false, remind_start: true, remind_end: true })
  editor.value?.showModal(); void loadTasks()
}
function fields(): ScheduleFields {
  const minutes = (value: string) => { const [h, m] = value.split(':').map(Number); return h! * 60 + m! }
  const start = minutes(form.start), end = form.midnight ? 1440 : minutes(form.end)
  if (!form.title.trim() || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) throw new Error('请填写名称，并让结束时间晚于开始时间；跨日安排请拆成两项。')
  return { title: form.title.trim(), notes: form.notes, start_minute: start, end_minute: end, task_id: form.task_id || null, timer_enabled: form.timer_enabled, remind_start: form.remind_start, remind_end: form.remind_end }
}
async function save() {
  if (busy.value) return
  busy.value = true; formError.value = ''
  try {
    const value = fields()
    if (selected.value) await editSchedule(selected.value.schedule_id, { ...value, scope: 'single', occurrence_date: selected.value.occurrence_date, revision: selected.value.revision, weekday: form.weekday })
    else await createSchedule({ ...value, weekday: form.weekday, effective_from: chosenWeekday.value, timezone: zone.value, repeat_weekly: false })
    editor.value?.close(); notice.value = '日程已保存。'; await load(); await runtime.sync()
  } catch (cause) { formError.value = cause instanceof Error && !('isAxiosError' in cause) ? cause.message : errorMessage(cause) }
  finally { busy.value = false }
}
function askRemove(item: Occurrence) { selected.value = item; formError.value = ''; deleting.value?.showModal() }
async function remove() {
  if (!selected.value || busy.value) return
  busy.value = true; formError.value = ''
  try {
    await removeSchedule(selected.value.schedule_id, { scope: 'single', occurrence_date: selected.value.occurrence_date, revision: selected.value.revision })
    deleting.value?.close(); notice.value = '已跳过本次，其他周不变。'
    await load(); await runtime.sync()
  } catch (cause) { formError.value = errorMessage(cause) }
  finally { busy.value = false }
}
onMounted(() => { void load(); void loadTemplates(); void checkReview(String(route.query.review || '')) })
watch(() => route.query.review, target => { void checkReview(String(target || '')) })
watch(today, () => { void checkReview() })
</script>

<template>
  <header class="page-header"><div><h1>每周日程</h1></div><button class="primary-button" :disabled="week < currentWeek || loading || busy" @click="open()">添加日程</button></header>
  <div class="week-controls"><button class="quiet" :disabled="loading || busy" @click="move(-1)">← 上一周</button><button class="quiet" :disabled="busy" @click="thisWeek">本周</button><button class="quiet" :disabled="loading || busy" @click="move(1)">下一周 →</button><strong>{{ week }} — {{ addDays(week, 6) }}</strong><button class="quiet" :disabled="loading || busy" @click="load">刷新</button></div>
  <div class="week-controls" aria-label="周模板">
    <strong>{{ templates.find(t => t.id === appliedTemplate)?.name || '未应用模板' }}</strong>
    <button class="quiet" :disabled="loading || busy || !!error" @click="openTemplate('save')">另存为新模板</button>
    <button class="quiet" :disabled="loading || busy || week < currentWeek || !templates.length" @click="openTemplate('apply')">应用模板</button>
    <button v-if="reviewWeek" class="quiet" :disabled="loading || busy" @click="keepWeek">
      {{ reviewWeek.planned_template_id ? '保留下周已选模板' : suggested ? `沿用「${suggested.name}」` : '保留下周安排' }}
    </button>
  </div>
  <p v-if="reviewWeek && !appliedTemplate && suggested" class="muted">周日未确认时，下周首次打开工作区会自动沿用「{{ suggested.name }}」。</p>
  <p class="muted schedule-help">按各日程保存的时区执行；新增默认 {{ zone }}。重叠日程会同时展示，但同一账号只运行一个计时。修改计划不会改变已经开始的计时。</p>
  <p v-if="error" class="form-error" role="alert">{{ error }}</p><p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  <p v-if="loading" role="status" class="muted">正在加载本周安排…</p>
  <div class="week-scroll"><div class="week-grid">
    <section v-for="(day, index) in days" :key="day" class="day-column" :class="{ today: day === dateInZone(runtime.now, zone) }" :aria-label="`${weekdays[index]} ${day}`">
      <header class="day-heading"><strong>{{ weekdays[index] }}</strong><span>{{ day.slice(5) }}</span><button v-if="day >= dateInZone(runtime.now, zone)" class="quiet" :aria-label="`添加 ${day} 日程`" @click="open(undefined, day)">＋</button></header>
      <p v-if="!items.some(item => item.occurrence_date === day)" class="muted day-empty">留一点自由时间</p>
      <article v-for="item in items.filter(row => row.occurrence_date === day)" :key="item.key" class="panel schedule-card" :class="{ skipped: item.skipped, 'in-progress': isCurrent(item) }">
        <span class="schedule-time">{{ minuteLabel(item.start_minute) }}–{{ minuteLabel(item.end_minute) }}</span><h2>{{ item.title }}</h2>
        <p v-if="item.timezone !== zone" class="muted">{{ item.timezone }}</p><p v-if="item.notes" class="schedule-notes">{{ item.notes }}</p>
        <p class="schedule-flags">{{ item.skipped ? '本次已跳过' : item.time_warning ? '时区跳转，时间无效' : isCurrent(item) ? '正在进行' : item.overridden ? '单次调整' : item.repeats ? '每周重复' : '当周日程' }}<span v-if="item.timer_enabled"> · 自动计时</span></p>
        <div v-if="editable(item)" class="schedule-actions"><button class="quiet" @click="open(item)">{{ item.skipped ? '恢复 / 编辑' : '编辑' }}</button><button class="quiet danger" @click="askRemove(item)">移除</button></div>
      </article>
    </section>
  </div></div>
  <dialog ref="templateDialog" class="schedule-dialog" aria-labelledby="template-dialog-title" @cancel="busy && $event.preventDefault()">
    <h2 id="template-dialog-title">{{ templateMode === 'save' ? '另存为新模板' : '应用日程模板' }}</h2>
    <form @submit.prevent="submitTemplate"><fieldset :disabled="busy">
      <template v-if="templateMode === 'save'">
        <label for="template-name">模板名称</label><input id="template-name" v-model.trim="templateName" required maxlength="80">
        <p class="muted">保存 {{ week }} 这周的安排，包含当周增删改后的结果。以后可选用此模板。</p>
      </template>
      <template v-else>
        <label for="template-choice">日程模板</label>
        <select id="template-choice" v-model="templateChoice" required><option v-for="template in templates" :key="template.id" :value="template.id">{{ template.name }}（{{ template.entry_count }} 项）</option></select>
        <p class="muted">将替换 {{ week }} 这周尚未开始的安排。已开始的日程与计时记录保留。后续未选模板的周会自动沿用。</p>
      </template>
      <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      <div class="schedule-actions"><button class="primary-button" type="submit">{{ templateMode === 'save' ? '保存为新模板' : '确认应用' }}</button><button class="quiet" type="button" @click="templateDialog?.close()">取消</button></div>
    </fieldset></form>
  </dialog>
  <dialog ref="editor" class="schedule-dialog" aria-labelledby="schedule-editor-title" @cancel="busy && $event.preventDefault()">
    <h2 id="schedule-editor-title">{{ selected ? '编辑日程' : '添加当周日程' }}</h2>
    <form @submit.prevent="save"><fieldset :disabled="busy">
      <label for="schedule-title">日程名称</label><input id="schedule-title" v-model="form.title" required maxlength="200" autofocus>
      <div class="schedule-form-grid"><div><label for="schedule-weekday">日期</label><select id="schedule-weekday" v-model.number="form.weekday" :disabled="!!selected"><option v-for="(day, i) in weekdays" :key="i" :value="i" :disabled="days[i]! < today">{{ day }} {{ days[i] }}</option></select></div></div>
      <div class="schedule-form-grid"><div><label for="schedule-start">开始时间</label><input id="schedule-start" v-model="form.start" type="time" required></div><div><label for="schedule-end">结束时间</label><input id="schedule-end" v-model="form.end" type="time" :disabled="form.midnight" :required="!form.midnight"></div></div>
      <label class="check-label"><input v-model="form.midnight" type="checkbox">当天 24:00 结束</label>
      <p class="muted">时区：{{ selected?.timezone || zone }}。单项安排限当天，跨日请拆分。</p>
      <label for="schedule-notes">备注</label><textarea id="schedule-notes" v-model="form.notes" rows="3" maxlength="10000"></textarea>
      <label for="schedule-task">关联任务（可选）</label><select id="schedule-task" v-model="form.task_id"><option value="">不关联任务</option><option v-if="form.task_id && !tasks.some(task => task.id === form.task_id)" :value="form.task_id">当前关联任务（尚未加载）</option><option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.title }}</option></select>
      <p v-if="taskError" class="form-error">{{ taskError }} <button type="button" class="quiet" @click="loadTasks()">重试</button></p><button v-if="tasks.length < taskTotal" type="button" class="quiet" @click="loadTasks(true)">加载更多任务</button>
      <label class="check-label"><input v-model="form.timer_enabled" type="checkbox">到点自动启用固定结束时间的计时</label><label class="check-label"><input v-model="form.remind_start" type="checkbox">开始提醒</label><label class="check-label"><input v-model="form.remind_end" type="checkbox">结束提醒</label>
      <p class="muted">网站运行时检测；晚打开时只记录剩余时段，已有计时则提示冲突。未开启自动计时的日程只用于规划。</p>
      <p v-if="formError" class="form-error" role="alert">{{ formError }}</p><div class="schedule-actions"><button class="primary-button" type="submit">{{ busy ? '保存中…' : '保存日程' }}</button><button type="button" class="quiet" @click="editor?.close()">返回</button></div>
    </fieldset></form>
  </dialog>
  <dialog ref="deleting" class="schedule-dialog" aria-labelledby="schedule-remove-title" @cancel="busy && $event.preventDefault()"><h2 id="schedule-remove-title">移除“{{ selected?.title }}”</h2><p class="muted">只跳过这一次，可重新编辑恢复。已产生的计时记录保留。</p><p v-if="formError" class="form-error" role="alert">{{ formError }}</p><div class="schedule-actions"><button class="quiet danger" :disabled="busy" @click="remove">确认移除</button><button class="quiet" :disabled="busy" @click="deleting?.close()">返回</button></div></dialog>
</template>

<style scoped>
.page-header .primary-button{width:auto;margin:0}
.week-controls,.schedule-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:18px 0}.week-controls strong{font-size:calc(14px * var(--ui-font-scale,1))}.quiet{padding:8px;border-radius:6px;font:inherit;cursor:pointer}.week-scroll{overflow-x:auto;padding-bottom:12px}.week-grid{display:grid;grid-template-columns:repeat(7,minmax(calc(112px * var(--ui-font-scale,1)),1fr));gap:10px}.day-column{min-width:0;border-top:1px solid rgba(127,127,127,.3)}.day-column.today{border-top:2px solid currentColor}.day-heading{display:flex;align-items:center;gap:8px;padding:10px 2px;font-size:calc(13px * var(--ui-font-scale,1))}.day-heading .quiet{margin-left:auto}.day-heading span{opacity:.8}.day-empty{padding:12px 2px}.schedule-card{padding:14px!important;border-radius:9px;margin:8px 0;overflow-wrap:anywhere}.schedule-card h2{font-size:calc(15px * var(--ui-font-scale,1));margin:12px 0}.schedule-time{font-size:calc(12px * var(--ui-font-scale,1));font-variant-numeric:tabular-nums}.schedule-notes{white-space:pre-wrap;font-size:calc(13px * var(--ui-font-scale,1));line-height:1.7}.schedule-flags{font-size:calc(11px * var(--ui-font-scale,1));line-height:1.7}.skipped{opacity:.6}.in-progress{border-left:3px solid currentColor!important}.schedule-actions{margin:12px 0 0;gap:8px}.schedule-actions button{font-size:calc(13px * var(--ui-font-scale,1))}.schedule-dialog{width:min(600px,calc(100vw - 32px));max-height:88vh;overflow:auto;padding:26px;border-radius:14px;color:var(--text-primary)}fieldset{border:0;margin:0;padding:0;min-width:0}.schedule-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}select{width:100%;padding:10px;font:inherit;border-radius:7px}.check-label{display:flex;align-items:center;gap:8px;font-size:calc(13px * var(--ui-font-scale,1));margin:16px 0}.check-label input{width:auto}.schedule-help{max-width:900px}@media(max-width:720px){.week-grid{grid-template-columns:1fr}.day-column{margin-bottom:16px}.schedule-form-grid{grid-template-columns:1fr}}
</style>
