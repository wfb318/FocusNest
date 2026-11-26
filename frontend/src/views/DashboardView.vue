<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getDashboard } from '../api/dashboard'
import { completeTask } from '../api/tasks'
import { startFocus } from '../api/focus'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { useReminders } from '../stores/reminders'
import { dateInZone, minuteLabel, secondsLabel } from '../utils/scheduleTime'
import type { Dashboard } from '../types/dashboard'
import LocalJournalStatus from '../components/LocalJournalStatus.vue'

const auth = useAuthStore(), runtime = useWorkspaceRuntime()
const data = ref<Dashboard | null>(null), loading = ref(false), error = ref(''), actionError = ref(''), notice = ref(''), acting = ref('')
let disposed = false, version = 0
let poll: ReturnType<typeof setInterval> | undefined
const priority = { high: '高优先级', medium: '中优先级', low: '低优先级' }
const kinds: Record<string, string> = { markdown: 'Markdown', text: 'TXT', pdf: 'PDF', word: 'Word', presentation: 'PPT', spreadsheet: 'Excel' }
const dateLabel = computed(() => data.value ? new Intl.DateTimeFormat('zh-CN', { timeZone: data.value.timezone, dateStyle: 'full' }).format(new Date(data.value.server_now)) : '')
const schedules = computed(() => runtime.occurrences.filter(item => !item.skipped && !item.time_warning && item.starts_at && dateInZone(Date.parse(item.starts_at), data.value?.timezone || auth.user?.timezone || 'Asia/Shanghai') === data.value?.today && Date.parse(item.ends_at!) > runtime.now).sort((a, b) => Date.parse(a.starts_at!) - Date.parse(b.starts_at!)).slice(0, 3))
const liveFocus = computed(() => {
  if (!data.value) return 0
  const same = runtime.current?.id === data.value.active_focus_id && runtime.current?.kind === 'focus'
  return Math.max(0, data.value.focus_seconds + (same ? runtime.elapsed - data.value.active_focus_seconds : 0))
})
function updated(value: string) { return new Intl.DateTimeFormat('zh-CN', { timeZone: data.value?.timezone || 'Asia/Shanghai', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) }
async function load() {
  if (loading.value || acting.value || disposed) return
  loading.value = true
  const request = ++version, userId = auth.user?.id
  try {
    const result = await getDashboard()
    if (!disposed && request === version && auth.user?.id === userId) { data.value = result; error.value = '' }
  } catch (cause) { if (!disposed && request === version) error.value = errorMessage(cause) }
  finally { if (request === version) loading.value = false }
}
async function finishTask(id: string) {
  if (acting.value || loading.value) return
  acting.value = id; actionError.value = ''; notice.value = ''
  try { await completeTask(id); if (!disposed) notice.value = '任务已完成。' }
  catch (cause) { if (!disposed) actionError.value = errorMessage(cause) }
  finally { acting.value = '' }
  await load()
}
async function quickFocus() {
  if (acting.value || !runtime.ready || runtime.error || runtime.current) return
  acting.value = 'focus'; actionError.value = ''; notice.value = ''
  try {
    const timer = await runtime.mutate(() => startFocus({ mode: 'pomodoro', kind: 'focus', title: '快速专注', duration_seconds: 1500, task_id: null }))
    void useReminders().notify(`timer:${timer.id}:start`, '快速专注：计时开始')
    if (!disposed) notice.value = '25 分钟专注已开始，可以留在工作台，也可以前往专注页。'
  } catch (cause) { if (!disposed) actionError.value = errorMessage(cause) }
  finally { acting.value = '' }
  await runtime.sync(); await load()
}
function visible() { if (document.visibilityState === 'visible') { void load(); void runtime.sync() } }
watch(() => auth.user?.timezone, () => { void load() })
watch(() => runtime.current?.id, () => { void load() })
watch(() => runtime.waiting, () => { void load() })
watch(() => data.value && dateInZone(runtime.now, data.value.timezone) !== data.value.today, changed => { if (changed) void load() })
onMounted(() => { void load(); poll = setInterval(visible, 60000); document.addEventListener('visibilitychange', visible); window.addEventListener('online', visible) })
onUnmounted(() => { disposed = true; ++version; clearInterval(poll); document.removeEventListener('visibilitychange', visible); window.removeEventListener('online', visible) })
</script>

<template>
  <header class="page-header"><div><span class="eyebrow">A CLEARER START TO YOUR DAY</span><h1>你好，{{ auth.user?.nickname || auth.user?.username }}。</h1><p class="muted">{{ dateLabel || '正在整理今天的工作台…' }}<span v-if="data"> · {{ data.timezone }}</span></p></div><button class="quiet" :disabled="loading || !!acting" @click="load">{{ loading ? '更新中…' : '刷新工作台' }}</button></header>
  <p v-if="error" class="form-error" role="alert">{{ error }} {{ data ? '当前显示上次获取的内容，请重试刷新。' : '请重试刷新工作台。' }}</p><p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p><p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  <p v-if="!data && loading" role="status" class="muted">正在载入任务、专注与最近记录…</p>
  <template v-if="data">
    <div class="dashboard-stats">
      <section class="panel stat"><span class="small-label">今日任务</span><strong>{{ data.task_done }} <small>/ {{ data.task_total }}</small></strong><p class="muted">{{ data.task_total ? '已完成 / 今日安排' : '今天还没有安排任务' }}<span v-if="data.overdue_tasks"> · {{ data.overdue_tasks }} 项已逾期</span></p><RouterLink to="/tasks">管理任务 →</RouterLink></section>
      <section class="panel stat"><span class="small-label">今日开始的专注</span><strong class="focus-value">{{ secondsLabel(liveFocus) }}</strong><p class="muted">{{ data.focus_completed }} 段已完成 · 含进行中与暂停，不含休息和取消</p><RouterLink to="/focus">查看专注记录 →</RouterLink></section>
      <LocalJournalStatus :date="data.today" :refresh-key="data.server_now" />
    </div>
    <div class="dashboard-grid">
      <section class="panel" aria-labelledby="dashboard-tasks"><div class="panel-heading"><h2 id="dashboard-tasks">今天值得投入的事</h2><RouterLink to="/tasks">全部任务 →</RouterLink></div><p class="muted hint">最多 5 项未完成任务，进行中和高优先级排在前面。</p>
        <ul v-if="data.tasks.length" class="overview-list"><li v-for="task in data.tasks" :key="task.id" class="task-row"><div><strong>{{ task.title }}</strong><p class="muted">{{ task.status === 'doing' ? '进行中' : '待办' }} · {{ priority[task.priority] }}<span v-if="task.due_date === data.today"> · 今日截止</span></p></div><button class="quiet" :aria-label="`完成任务：${task.title}`" :disabled="!!acting || loading" @click="finishTask(task.id)">{{ acting === task.id ? '处理中…' : '完成' }}</button></li></ul>
        <div v-else class="empty"><h3>{{ data.task_total ? '今天安排的任务已全部完成' : '先给今天安排一件事' }}</h3><p class="muted">{{ data.task_total ? '可以留一点时间休息，或继续自己的计划。' : '为任务设置今天的计划日期或截止日期，就会出现在这里。' }}</p><RouterLink to="/tasks">前往任务页 →</RouterLink></div>
      </section>
      <section class="panel" aria-labelledby="dashboard-focus"><div class="panel-heading"><h2 id="dashboard-focus">留一段专注时间</h2><RouterLink to="/focus">更多计时方式 →</RouterLink></div>
        <template v-if="runtime.current"><h3>{{ runtime.current.title || (runtime.current.kind === 'break' ? '正在休息' : '当前专注') }}</h3><div class="dashboard-clock" role="timer">{{ secondsLabel(runtime.displaySeconds) }}</div><p class="muted">{{ runtime.waiting ? '距离开始' : runtime.current.status === 'paused' ? '已暂停' : runtime.current.mode === 'stopwatch' ? '已用时间' : '剩余时间' }}</p><RouterLink to="/focus">前往专注页管理 →</RouterLink></template>
        <template v-else><p class="invitation">把眼前的一件事，做得从容一点。</p><p class="muted">一键开始 25 分钟番茄钟。需要关联任务或指定起止时间，可前往专注页设置。</p><button class="primary-button quick-focus" :disabled="!!acting || !runtime.ready || !!runtime.error || runtime.mutating" @click="quickFocus">{{ acting === 'focus' ? '启动中…' : '开始 25 分钟专注' }}</button></template><p v-if="runtime.error" class="form-error">计时状态尚未同步，请先在右侧重试同步。</p>
      </section>
      <section class="panel" aria-labelledby="dashboard-notes"><div class="panel-heading"><h2 id="dashboard-notes">最近笔记</h2><RouterLink to="/notes">全部笔记 →</RouterLink></div><ul v-if="data.recent_notes.length" class="overview-list"><li v-for="note in data.recent_notes" :key="note.id"><RouterLink :to="{ path: '/notes', query: { note: note.id } }" class="recent-link"><strong>{{ note.title }}</strong><span class="muted">{{ note.pinned ? '置顶 · ' : '' }}{{ updated(note.updated_at) }}</span></RouterLink></li></ul><div v-else class="empty"><p class="muted">还没有笔记，从一个想法开始。</p><RouterLink to="/notes">写一篇笔记 →</RouterLink></div></section>
      <section class="panel" aria-labelledby="dashboard-documents"><div class="panel-heading"><h2 id="dashboard-documents">最近文档</h2><RouterLink to="/documents">全部资料 →</RouterLink></div><ul v-if="data.recent_documents.length" class="overview-list"><li v-for="doc in data.recent_documents" :key="doc.id"><RouterLink :to="{ path: '/documents', query: { document: doc.id } }" class="recent-link"><strong>{{ doc.title }}</strong><span class="muted">{{ kinds[doc.kind] || doc.kind }} · {{ updated(doc.updated_at) }}</span></RouterLink></li></ul><div v-else class="empty"><p class="muted">保存常用阅读资料，随时接着看。</p><RouterLink to="/documents">导入一份文档 →</RouterLink></div></section>
      <section class="panel schedule-overview" aria-labelledby="dashboard-schedule"><div class="panel-heading"><h2 id="dashboard-schedule">接下来的日程</h2><RouterLink to="/schedule">每周规划 →</RouterLink></div><p v-if="!runtime.ready" class="muted">日程正在同步…</p><ul v-else-if="schedules.length" class="overview-list"><li v-for="item in schedules" :key="item.key" class="schedule-row"><span>{{ minuteLabel(item.start_minute) }}–{{ minuteLabel(item.end_minute) }}</span><div><strong>{{ item.title }}</strong><p class="muted">{{ item.timezone }} · {{ Date.parse(item.starts_at!) <= runtime.now ? '正在进行' : '稍后开始' }}{{ item.timer_enabled ? ' · 自动计时' : '' }}</p></div></li></ul><p v-else class="muted">今天接下来没有日程，按自己的节奏安排。</p><p v-if="runtime.error" class="form-error">{{ runtime.error }} 日程显示可能已过期。</p></section>
    </div>
    <footer class="muted dashboard-footer">上次汇总 {{ updated(data.server_now) }} · 约每分钟更新，切回页面时同步。专注按今日开始的会话累计，跨日会话计入开始日。</footer>
  </template>
</template>

<style scoped>
h1{margin:12px 0}.quiet{padding:9px 12px;border-radius:7px;font:inherit;font-size:calc(13px * var(--ui-font-scale,1));cursor:pointer}.dashboard-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin:26px 0}.stat,.dashboard-grid>.panel{padding:24px!important;min-width:0;overflow-wrap:anywhere}.stat{display:flex;flex-direction:column;align-items:flex-start}.stat>strong{font-size:calc(34px * var(--ui-font-scale,1));font-weight:500;margin:22px 0 6px;font-variant-numeric:tabular-nums}.stat>strong small{font-size:calc(18px * var(--ui-font-scale,1));opacity:.7}.stat>strong.focus-value{font-size:calc(28px * var(--ui-font-scale,1))}.stat>strong.journal-value{font-size:calc(24px * var(--ui-font-scale,1))}.stat p,.hint{font-size:calc(12px * var(--ui-font-scale,1))}.stat a{margin-top:auto}.dashboard-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.dashboard-grid h2{margin:0}.dashboard-grid a,.stat a{font-size:calc(13px * var(--ui-font-scale,1));text-decoration:underline;text-underline-offset:4px}.overview-list{list-style:none;padding:0;margin:16px 0 0}.overview-list>li{padding:15px 0;border-bottom:1px solid rgba(127,127,127,.16)}.overview-list>li:last-child{border:0}.overview-list strong{font-size:calc(14px * var(--ui-font-scale,1));font-weight:550;line-height:1.7}.task-row,.schedule-row{display:flex;align-items:center;justify-content:space-between;gap:18px}.task-row>div{min-width:0}.task-row p,.schedule-row p{font-size:calc(12px * var(--ui-font-scale,1));margin:5px 0 0}.task-row button{flex-shrink:0}.recent-link{display:flex;flex-direction:column;gap:8px;text-decoration:none!important}.recent-link:hover strong{text-decoration:underline}.recent-link span{font-size:calc(12px * var(--ui-font-scale,1))}.empty{padding:20px 0 8px}h3{font-size:calc(17px * var(--ui-font-scale,1));font-weight:500}.dashboard-clock{font-size:calc(38px * var(--ui-font-scale,1));font-variant-numeric:tabular-nums;margin-top:22px}.invitation{font-size:calc(20px * var(--ui-font-scale,1));line-height:1.7;margin-top:28px}.quick-focus{width:auto;margin-top:16px}.schedule-overview{grid-column:1/-1}.schedule-row{justify-content:flex-start}.schedule-row>span{font-size:calc(13px * var(--ui-font-scale,1));font-variant-numeric:tabular-nums;flex-shrink:0}.dashboard-footer{font-size:calc(12px * var(--ui-font-scale,1));margin:24px 0}@media(max-width:1000px){.dashboard-stats{grid-template-columns:1fr}.stat>strong{margin-top:12px}.dashboard-grid{grid-template-columns:1fr}}@media(max-width:480px){.task-row,.schedule-row{align-items:flex-start;flex-wrap:wrap}.dashboard-grid>.panel,.stat{padding:20px!important}}
</style>
