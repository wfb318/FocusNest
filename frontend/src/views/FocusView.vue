<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { changeFocus, focusHistory, startFocus } from '../api/focus'
import { listTasks } from '../api/tasks'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { FocusAction, FocusMode, FocusSession } from '../types/focus'
import type { Task } from '../types/task'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { useReminders } from '../stores/reminders'
import { zonedInstant } from '../utils/scheduleTime'
import TimerSoundControl from '../components/TimerSoundControl.vue'

const auth = useAuthStore()
const runtime = useWorkspaceRuntime()
const current = computed(() => runtime.current)
const records = ref<FocusSession[]>([])
const tasks = ref<Task[]>([])
const taskPage = ref(1)
const taskTotal = ref(0)
const page = ref(1)
const total = ref(0)
const busy = ref(false)
const ready = ref(false)
const syncing = ref(false)
const error = ref('')
const taskError = ref('')
const notice = ref('')
let disposed = false
let generation = 0
const cancelDialog = ref<HTMLDialogElement | null>(null)
const form = reactive({ mode: 'pomodoro' as FocusMode, minutes: 25, breakMinutes: 5, taskId: '', title: '', windowStart: '', windowEnd: '' })
const modes = { pomodoro: '番茄钟', countdown: '倒计时', stopwatch: '正计时', scheduled: '指定起止时间' }
const statuses = { scheduled: '等待开始', running: '进行中', paused: '已暂停', completed: '已完成', cancelled: '已取消' }
const pages = computed(() => Math.max(1, Math.ceil(total.value / 10)))
const elapsed = computed(() => runtime.elapsed)
const displaySeconds = computed(() => Math.ceil(runtime.displaySeconds))
const progress = computed(() => current.value?.duration_seconds ? elapsed.value / current.value.duration_seconds * 100 : 0)
function duration(seconds: number) {
  const value = Math.max(0, Math.floor(seconds))
  return [Math.floor(value / 3600), Math.floor(value / 60) % 60, value % 60].map(n => String(n).padStart(2, '0')).join(':')
}
function localTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { timeZone: auth.user?.timezone || 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
function taskName(id: string | null) { return id ? tasks.value.find(task => task.id === id)?.title || '关联任务（未载入名称）' : '未关联任务 / 原任务已删除' }
function applyCurrent(value: FocusSession | null) {
  const previous = current.value
  runtime.apply(value)
  if (previous && !value && previous.status === 'running') notice.value = '计时已结束或已在其他页面处理，请查看下方记录。'
}
async function sync() {
  if (busy.value || syncing.value || disposed) return
  const version = ++generation
  syncing.value = true
  try {
    await runtime.sync()
    if (!runtime.ready || runtime.error) { error.value = runtime.error || '正在恢复全局计时，请稍后重试。'; return }
    const history = await focusHistory(page.value)
    if (disposed || version !== generation) return
    records.value = history.items
    total.value = history.total
    ready.value = true
    error.value = ''
  } catch (cause) { if (!disposed && version === generation) error.value = errorMessage(cause) }
  finally { syncing.value = false }
}
async function loadTasks(more = false) {
  const next = more ? taskPage.value + 1 : 1
  taskError.value = ''
  try {
    const result = await listTasks({ page: next, page_size: 100 })
    if (disposed) return
    tasks.value = more ? [...tasks.value, ...result.items] : result.items
    taskPage.value = next
    taskTotal.value = result.total
  } catch (cause) { taskError.value = errorMessage(cause) }
}
async function start(kind: 'focus' | 'break' = 'focus') {
  if (busy.value || syncing.value || !ready.value) return
  const minutes = kind === 'break' ? form.breakMinutes : form.minutes
  const mode = kind === 'break' ? 'pomodoro' : form.mode
  if (!['stopwatch', 'scheduled'].includes(mode) && (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440)) {
    error.value = '时长请填写 1–1440 的整数分钟。'; return
  }
  busy.value = true; ++generation; notice.value = ''; error.value = ''
  try {
    const times = mode === 'scheduled' ? { window_start: zonedInstant(form.windowStart, auth.user?.timezone || 'Asia/Shanghai'), window_end: zonedInstant(form.windowEnd, auth.user?.timezone || 'Asia/Shanghai') } : {}
    const started = await runtime.mutate(() => startFocus({ mode, kind, title: form.title.trim(), duration_seconds: ['stopwatch', 'scheduled'].includes(mode) ? null : minutes * 60, task_id: kind === 'focus' ? form.taskId || null : null, ...times }))
    applyCurrent(started)
    if (started.status === 'running' && !started.occurrence_key) void useReminders().notify(`timer:${started.id}:start`, `${started.title || '专注'}：计时开始`)
    page.value = 1
    notice.value = started.status === 'scheduled' ? '计时已安排，到点后自动开始。' : kind === 'break' ? '休息已开始。休息时间单独记录。' : '专注已开始。'
  } catch (cause) { error.value = cause instanceof Error && !('isAxiosError' in cause) ? cause.message : errorMessage(cause) }
  finally { busy.value = false }
  // Preserve action failures while still recovering an ambiguous network result.
  const actionError = error.value
  await sync()
  if (actionError) error.value = actionError
}
async function act(action: FocusAction) {
  if (!current.value || busy.value || syncing.value) return
  busy.value = true; ++generation; notice.value = ''; error.value = ''
  try {
    const id = current.value.id
    const result = await runtime.mutate(() => changeFocus(id, action))
    applyCurrent(['scheduled', 'running', 'paused'].includes(result.status) ? result : null)
    notice.value = `计时${statuses[result.status]}。`
    cancelDialog.value?.close()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
  const actionError = error.value
  await sync()
  if (actionError) error.value = actionError
}
function changePage(value: number) { if (busy.value || syncing.value) return; page.value = value; void sync() }
function visible() { if (document.visibilityState === 'visible') void sync() }
function closeCancel() { if (!busy.value) cancelDialog.value?.close() }
watch(() => runtime.current?.id, () => { if (!disposed && !busy.value) void sync() })
onMounted(() => {
  void sync(); void loadTasks()
  document.addEventListener('visibilitychange', visible)
  window.addEventListener('online', visible)
})
onUnmounted(() => {
  disposed = true; ++generation
  document.removeEventListener('visibilitychange', visible)
  window.removeEventListener('online', visible)
})
</script>

<template>
  <header class="page-header"><div><span class="eyebrow">ONE THING AT A TIME</span><h1>专注</h1><p class="muted">给眼前的一件事，留一段完整的时间。</p></div><button class="quiet" :disabled="busy || syncing" @click="sync">{{ syncing ? '同步中…' : '同步计时' }}</button></header>
  <TimerSoundControl />
  <p v-if="error" class="form-error" role="alert">{{ error }} 连接恢复后可点击“同步计时”。</p>
  <p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  <section v-if="current" class="panel timer-panel" aria-label="当前计时">
    <div class="timer-top"><span>{{ modes[current.mode] }} · {{ current.kind === 'break' ? '休息' : '专注' }}</span><span>{{ runtime.waiting ? '等待开始' : current.status === 'scheduled' ? '进行中' : statuses[current.status] }}</span></div>
    <h2 v-if="current.title">{{ current.title }}</h2>
    <div class="clock" role="timer" aria-label="计时时间">{{ duration(displaySeconds) }}</div>
    <p class="muted">{{ runtime.waiting ? '距离开始' : current.duration_seconds || current.mode === 'scheduled' ? '剩余时间' : '已专注时间' }} · 已累计 {{ duration(elapsed) }}</p>
    <p v-if="current.window_start && current.window_end" class="muted">{{ localTime(current.window_start) }} — {{ localTime(current.window_end) }}</p>
    <progress v-if="current.duration_seconds" :value="progress" max="100" aria-label="计时进度"></progress>
    <p v-if="current.kind === 'focus'" class="task-name">{{ taskName(current.task_id) }}</p>
    <p v-if="current.duration_seconds && displaySeconds === 0" class="muted">本轮已到时，正在等待服务端确认…</p>
    <div class="buttons">
      <button v-if="current.mode !== 'scheduled'" class="quiet" :disabled="busy || syncing" @click="act(current.status === 'paused' ? 'resume' : 'pause')">{{ current.status === 'paused' ? '继续计时' : '暂停计时' }}</button>
      <button class="primary-button" :disabled="busy || syncing || runtime.waiting" @click="act('finish')">结束并保存</button>
      <button class="quiet danger" :disabled="busy || syncing" @click="cancelDialog?.showModal()">取消本次</button>
    </div>
    <p class="muted small">{{ current.mode === 'scheduled' ? '固定结束时间不会随暂停顺延，可提前结束或取消；等待开始期间不累计。' : '暂停期间不累计时间。' }}刷新或关闭页面后仍保留计时；结束专注不会自动完成关联任务。</p>
  </section>
  <section v-else class="panel setup-panel" aria-label="开始专注">
    <h2>{{ ready ? '选择你的节奏' : '正在恢复计时…' }}</h2>
    <form @submit.prevent="start('focus')"><fieldset :disabled="busy || syncing || !ready">
      <label for="focus-mode">计时方式</label><select id="focus-mode" v-model="form.mode"><option v-for="(label, mode) in modes" :key="mode" :value="mode">{{ label }}</option></select>
      <label for="focus-title">计时内容（可选）</label><input id="focus-title" v-model="form.title" maxlength="200" placeholder="这段时间想做什么？">
      <div v-if="form.mode === 'scheduled'" class="form-grid"><div><label for="focus-start">开始时间</label><input id="focus-start" v-model="form.windowStart" type="datetime-local" required></div><div><label for="focus-end">结束时间</label><input id="focus-end" v-model="form.windowEnd" type="datetime-local" required></div></div>
      <p v-if="form.mode === 'scheduled'" class="muted small">按 {{ auth.user?.timezone }} 解释时间，时段为 1 分钟至 24 小时；开始时间可在未来 31 天内。结束时间固定，不提供暂停。晚启动只累计启动后的时间。</p>
      <div class="form-grid"><div v-if="!['stopwatch','scheduled'].includes(form.mode)"><label for="focus-minutes">专注时长（分钟）</label><input id="focus-minutes" v-model.number="form.minutes" type="number" min="1" max="1440" step="1" required></div><div v-if="form.mode === 'pomodoro'"><label for="break-minutes">休息时长（分钟）</label><input id="break-minutes" v-model.number="form.breakMinutes" type="number" min="1" max="1440" step="1" required></div></div>
      <label for="focus-task">关联任务（可选）</label><select id="focus-task" v-model="form.taskId"><option value="">不关联任务</option><option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.title }}{{ task.status === 'done' ? '（已完成）' : '' }}</option></select>
      <p v-if="taskError" class="form-error">{{ taskError }} <button type="button" class="quiet" @click="loadTasks()">重试加载任务</button></p>
      <button v-if="tasks.length < taskTotal" type="button" class="quiet" @click="loadTasks(true)">加载更多任务（{{ tasks.length }}/{{ taskTotal }}）</button>
      <div class="buttons"><button class="primary-button" type="submit">开始专注</button><button v-if="form.mode === 'pomodoro'" class="quiet" type="button" @click="start('break')">开始休息</button></div>
      <p class="muted small">番茄钟默认专注 25 分钟、休息 5 分钟。每轮结束后手动开始下一轮；休息单独记录。同一账号同时只能有一个计时。</p>
    </fieldset></form>
  </section>
  <section class="history" aria-label="专注记录"><div class="panel-heading"><h2>专注与休息记录</h2><span class="muted">共 {{ total }} 条 · {{ auth.user?.timezone }}</span></div>
    <p v-if="ready && !records.length" class="panel muted">还没有记录，从一段专注开始。</p>
    <ul v-else class="records"><li v-for="record in records" :key="record.id" class="panel record"><div><strong>{{ modes[record.mode] }} · {{ record.kind === 'break' ? '休息' : '专注' }}</strong><p v-if="record.title">{{ record.title }}</p><p class="muted">{{ localTime(record.started_at) }}</p><p v-if="record.kind === 'focus'" class="task-name">{{ taskName(record.task_id) }}</p></div><div class="record-result"><span>{{ statuses[record.status] }}</span><strong>{{ duration(record.elapsed_seconds) }}</strong><small v-if="record.duration_seconds" class="muted">目标 {{ duration(record.duration_seconds) }}</small></div></li></ul>
    <nav class="buttons pagination" aria-label="记录分页"><button class="quiet" :disabled="page <= 1 || busy || syncing" @click="changePage(page - 1)">上一页</button><span>{{ page }} / {{ pages }}</span><button class="quiet" :disabled="page >= pages || busy || syncing" @click="changePage(page + 1)">下一页</button></nav>
  </section>
  <dialog ref="cancelDialog" aria-labelledby="cancel-title" @cancel.prevent="closeCancel"><h2 id="cancel-title">取消本次计时？</h2><p class="muted">已用时间会保留为“已取消”记录，不算作完成。</p><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="buttons"><button class="quiet" autofocus :disabled="busy" @click="closeCancel">返回</button><button class="quiet danger" :disabled="busy || syncing" @click="act('cancel')">确认取消</button></div></dialog>
</template>

<style scoped>
h1{margin:12px 0}.timer-panel,.setup-panel{margin-top:22px}.timer-panel{text-align:center;padding:32px}.timer-top{display:flex;justify-content:space-between;color:var(--text-muted,#586d60);font-size:calc(14px * var(--ui-font-scale,1))}.clock{font-size:clamp(calc(46px * var(--ui-font-scale,1)),calc(8vw * var(--ui-font-scale,1)),calc(84px * var(--ui-font-scale,1)));font-variant-numeric:tabular-nums;letter-spacing:3px;margin:30px 0 4px;color:var(--text-primary,#263c34)}.buttons{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:20px}.timer-panel .buttons{justify-content:center}.primary-button{width:auto;margin:0}.quiet{border:1px solid #d7dfd5;background:#fff;color:var(--text-primary,#263c34);border-radius:8px;padding:11px 16px}.danger{color:#ad4141}.small{font-size:calc(12px * var(--ui-font-scale,1));margin-top:24px}.task-name{overflow-wrap:anywhere;font-size:calc(14px * var(--ui-font-scale,1));color:var(--text-muted,#586d60)}progress{display:block;width:100%;height:8px;accent-color:#39765c;margin:25px 0}fieldset{border:0;margin:0;padding:0;min-width:0}select{width:100%;padding:12px;border:1px solid #d7dfd5;background:#fcfdfb;border-radius:8px;color:var(--text-primary,#263c34);font:inherit;font-size:calc(14px * var(--ui-font-scale,1))}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.history{margin-top:36px}.records{padding:0;list-style:none;display:grid;gap:12px}.record{display:flex;justify-content:space-between;gap:20px;padding:22px}.record p{margin:8px 0}.record-result{display:flex;flex-direction:column;gap:10px;align-items:flex-end;flex-shrink:0;font-size:calc(13px * var(--ui-font-scale,1))}.record-result strong{font-size:calc(22px * var(--ui-font-scale,1));font-variant-numeric:tabular-nums}.pagination{justify-content:center;font-size:calc(13px * var(--ui-font-scale,1))}dialog{max-width:440px;width:calc(100% - 40px);padding:26px;border:1px solid #d7dfd5;border-radius:14px;color:var(--text-primary,#263c34)}dialog::backdrop{background:rgb(30 50 40 / 35%)}@media(max-width:480px){.form-grid{grid-template-columns:1fr;gap:0}.timer-panel{padding:22px 16px}.record{flex-direction:column}.record-result{align-items:flex-start;flex-direction:row;flex-wrap:wrap}.clock{letter-spacing:0}}
</style>
