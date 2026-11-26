<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { getStatistics } from '../api/statistics'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { dateInZone, secondsLabel } from '../utils/scheduleTime'
import { durationLabel, statisticsRange } from '../utils/statistics'
import type { FocusMode, Statistics } from '../types/statistics'

const auth = useAuthStore()
const zone = computed(() => auth.user?.timezone || 'Asia/Shanghai')
const today = ref(dateInZone(Date.now(), zone.value))
const preset = ref<'week' | 'month' | 'custom'>('week')
const range = reactive(statisticsRange('week', today.value))
const data = ref<Statistics | null>(null), loading = ref(false), error = ref('')
const selectedDate = ref(''), metric = ref<'seconds' | 'completed'>('seconds')
const modeNames: Record<FocusMode, string> = {
  pomodoro: '番茄钟', countdown: '倒计时', stopwatch: '正计时', scheduled: '定时专注',
}
const selected = computed(() => data.value?.daily.find(day => day.date === selectedDate.value))
const maximum = computed(() => Math.max(1, ...(data.value?.daily.map(day => day[metric.value]) ?? [])))
const statusRows = computed(() => data.value ? [
  { label: '待办', value: data.value.tasks.todo, status: 'todo' },
  { label: '进行中', value: data.value.tasks.doing, status: 'doing' },
  { label: '已完成', value: data.value.tasks.done, status: 'done' },
] : [])
let disposed = false, version = 0
let poll: ReturnType<typeof setInterval> | undefined

async function load() {
  if (disposed) return
  const request = ++version, owner = auth.user?.id
  const query = { ...range }
  loading.value = true; error.value = ''; data.value = null
  try {
    const result = await getStatistics(query)
    if (disposed || request !== version || auth.user?.id !== owner) return
    data.value = result
    if (!result.daily.some(day => day.date === selectedDate.value)) {
      selectedDate.value = result.daily.find(day => day.date === result.today)?.date || result.end_date
    }
  } catch (cause) { if (!disposed && request === version) error.value = errorMessage(cause) }
  finally { if (request === version) loading.value = false }
}
function choosePreset(value: 'week' | 'month') {
  preset.value = value
  today.value = dateInZone(Date.now(), zone.value)
  Object.assign(range, statisticsRange(value, today.value))
  void load()
}
function customRange() { preset.value = 'custom' }
function refresh() {
  if (loading.value || document.visibilityState !== 'visible') return
  if (!data.value || range.start_date !== data.value.start_date || range.end_date !== data.value.end_date) return
  const date = dateInZone(Date.now(), zone.value)
  if (date !== today.value) {
    today.value = date
    if (preset.value !== 'custom') Object.assign(range, statisticsRange(preset.value, date))
  }
  void load()
}
function updated(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: data.value?.timezone || zone.value, month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}
watch(zone, () => {
  today.value = dateInZone(Date.now(), zone.value)
  if (preset.value !== 'custom') Object.assign(range, statisticsRange(preset.value, today.value))
  void load()
})
onMounted(() => {
  void load()
  poll = setInterval(refresh, 60_000)
  document.addEventListener('visibilitychange', refresh)
  window.addEventListener('online', refresh)
})
onUnmounted(() => {
  disposed = true; ++version; clearInterval(poll)
  document.removeEventListener('visibilitychange', refresh)
  window.removeEventListener('online', refresh)
})
</script>

<template>
  <header class="page-header">
    <div><h1>统计</h1><p class="muted">回看投入的时间和任务进展。</p></div>
    <button class="quiet" :disabled="loading" @click="load">{{ loading ? '更新中…' : '刷新统计' }}</button>
  </header>
  <form class="range-controls" aria-label="统计日期范围" @submit.prevent="load">
    <div class="presets" aria-label="快捷日期">
      <button type="button" class="quiet" :aria-pressed="preset === 'week'" @click="choosePreset('week')">本周</button>
      <button type="button" class="quiet" :aria-pressed="preset === 'month'" @click="choosePreset('month')">本月</button>
    </div>
    <label for="statistics-start">开始日期<input id="statistics-start" v-model="range.start_date" type="date" min="1900-01-01" max="9998-12-31" required @input="customRange"></label>
    <label for="statistics-end">结束日期<input id="statistics-end" v-model="range.end_date" type="date" :min="range.start_date || '1900-01-01'" max="9998-12-31" required @input="customRange"></label>
    <button class="quiet" type="submit" :disabled="loading">查询</button>
  </form>
  <p v-if="loading" class="muted" role="status">正在汇总专注与任务…</p>
  <p v-if="error" class="form-error" role="alert">{{ error }} <button class="quiet" @click="load">重试</button></p>
  <template v-if="data">
    <p class="range-caption muted">{{ data.start_date }} — {{ data.end_date }} · {{ data.timezone }}</p>
    <div class="statistics-cards">
      <section class="panel summary"><span>专注时长</span><strong>{{ durationLabel(data.focus.seconds) }}</strong><p class="muted">{{ data.focus.active ? `含 ${data.focus.active} 段进行中或暂停的专注` : '按专注开始日期归属' }}</p></section>
      <section class="panel summary"><span>完成专注</span><strong>{{ data.focus.completed }} <small>次</small></strong><p class="muted">按开始日统计完成的会话</p></section>
      <section class="panel summary"><span>期间新建任务</span><strong>{{ data.tasks.total }} <small>项</small></strong><p class="muted">以任务创建时间筛选</p></section>
      <section class="panel summary"><span>任务完成率</span><strong>{{ data.tasks.completion_rate === null ? '—' : `${data.tasks.completion_rate}%` }}</strong><p class="muted">{{ data.tasks.total ? `${data.tasks.done} / ${data.tasks.total} 项目前已完成` : '此范围还没有新建任务' }}</p></section>
    </div>
    <section class="panel focus-trend" aria-labelledby="statistics-trend">
      <div class="section-heading">
        <div><h2 id="statistics-trend">每日专注</h2><p class="muted">选择一天查看数值，长日期范围可横向滚动。</p></div>
        <div class="presets"><button class="quiet" :aria-pressed="metric === 'seconds'" @click="metric = 'seconds'">时长</button><button class="quiet" :aria-pressed="metric === 'completed'" @click="metric = 'completed'">完成次数</button></div>
      </div>
      <div class="chart-scroll" role="group" :aria-label="metric === 'seconds' ? '每日专注时长' : '每日专注完成次数'">
        <div class="daily-chart" :style="{ gridTemplateColumns: `repeat(${data.daily.length}, minmax(28px, 1fr))` }">
          <button v-for="day in data.daily" :key="day.date" class="day-bar" :class="{ selected: selectedDate === day.date, future: day.date > data.today }" :aria-pressed="selectedDate === day.date" :aria-label="`${day.date}，${durationLabel(day.seconds)}，完成 ${day.completed} 次`" :title="`${day.date} · ${durationLabel(day.seconds)} · ${day.completed} 次`" @click="selectedDate = day.date">
            <span class="bar-track"><span class="bar-fill" :style="{ height: day[metric] ? `${Math.max(2, day[metric] / maximum * 100)}%` : '0' }"></span></span>
            <span class="bar-date">{{ data.daily.length <= 31 || day.date.endsWith('-01') ? day.date.slice(5) : day.date.slice(8) }}</span>
          </button>
        </div>
      </div>
      <p v-if="selected" class="day-detail" aria-live="polite">{{ selected.date }} · {{ durationLabel(selected.seconds) }} · 完成 {{ selected.completed }} 次<span v-if="selected.active"> · {{ selected.active }} 段进行中或暂停</span></p>
      <p v-if="data.focus.seconds === 0" class="muted">这个范围尚无累计专注时长。</p>
    </section>
    <div class="statistics-details">
      <section class="panel" aria-labelledby="statistics-modes">
        <h2 id="statistics-modes">专注方式</h2>
        <ul class="breakdown"><li v-for="mode in data.modes" :key="mode.mode">
          <div class="breakdown-label"><span>{{ modeNames[mode.mode] }}</span><strong>{{ durationLabel(mode.seconds) }}</strong></div>
          <div class="meter"><span :style="{ width: data.focus.seconds ? `${mode.seconds / data.focus.seconds * 100}%` : '0' }"></span></div>
          <p class="muted">{{ mode.completed }} 次完成<span v-if="mode.active"> · {{ mode.active }} 段进行中或暂停</span></p>
        </li></ul>
      </section>
      <section class="panel" aria-labelledby="statistics-tasks">
        <h2 id="statistics-tasks">任务进展</h2><p class="muted">期间新建任务的当前状态。</p>
        <ul class="breakdown"><li v-for="item in statusRows" :key="item.status">
          <div class="breakdown-label"><span>{{ item.label }}</span><strong>{{ item.value }} 项</strong></div>
          <div class="meter" :class="item.status"><span :style="{ width: data.tasks.total ? `${item.value / data.tasks.total * 100}%` : '0' }"></span></div>
        </li></ul>
        <p class="overdue">{{ data.tasks.overdue }} 项当前已逾期</p><p class="muted">逾期指截止日期早于今天且尚未完成。</p>
        <RouterLink to="/tasks">管理任务 →</RouterLink>
      </section>
    </div>
    <details class="statistics-rules">
      <summary>统计口径与每日明细</summary>
      <p>专注按账号时区的开始日累计，跨日会话全部计入开始日。包含完成、进行中和暂停的有效时长，暂停阶段不累计，休息与取消会话不计入。当前专注以本次刷新时的时长为准。</p>
      <p>任务按创建日期筛选，状态反映当前结果。恢复任务或删除记录后，历史范围的汇总会更新。日期包含首尾两天，最多查询 366 天。</p>
      <div class="table-scroll"><table><caption>每日专注明细</caption><thead><tr><th scope="col">日期</th><th scope="col">有效时长</th><th scope="col">完成次数</th></tr></thead><tbody><tr v-for="day in data.daily" :key="day.date"><th scope="row">{{ day.date }}</th><td>{{ secondsLabel(day.seconds) }}</td><td>{{ day.completed }}</td></tr></tbody></table></div>
    </details>
    <p class="updated muted">更新于 {{ updated(data.server_now) }} · 约每分钟刷新，切回页面时同步。</p>
  </template>
</template>

<style scoped>
.quiet {
  padding:9px 12px;
  border-radius:7px;
  font:inherit;
  font-size:calc(13px * var(--ui-font-scale,1));
  cursor:pointer
}
.quiet[aria-pressed=true] {
  box-shadow:inset 0 -2px currentColor
}
.range-controls {
  display:flex;
  align-items:end;
  flex-wrap:wrap;
  gap:14px;
  margin:24px 0
}
.range-controls label {
  display:grid;
  gap:6px;
  margin:0;
  font-size:calc(13px * var(--ui-font-scale,1))
}
.range-controls input {
  width:auto;
  margin:0
}
.presets {
  display:flex;
  gap:8px
}
.range-caption {
  font-size:calc(12px * var(--ui-font-scale,1))
}
.statistics-cards {
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:16px;
  margin:20px 0
}
.summary,.focus-trend,.statistics-details>.panel {
  padding:24px!important;
  min-width:0;
  overflow-wrap:anywhere
}
.summary>span,.summary p {
  font-size:calc(12px * var(--ui-font-scale,1))
}
.summary strong {
  display:block;
  font-size:calc(27px * var(--ui-font-scale,1));
  font-weight:500;
  font-variant-numeric:tabular-nums;
  margin:20px 0 10px
}
.summary small {
  font-size:calc(14px * var(--ui-font-scale,1))
}
.summary p {
  margin-bottom:0;
  line-height:1.7
}
.section-heading {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:20px;
  flex-wrap:wrap
}
h2 {
  font-size:calc(18px * var(--ui-font-scale,1));
  font-weight:550;
  margin:0
}
.section-heading p {
  font-size:calc(12px * var(--ui-font-scale,1));
  margin:10px 0 0
}
.chart-scroll {
  overflow-x:auto;
  margin-top:24px
}
.daily-chart {
  display:grid;
  gap:6px;
  min-height:210px
}
.day-bar {
  display:flex;
  flex-direction:column;
  gap:9px;
  align-items:center;
  justify-content:end;
  border:0!important;
  border-radius:4px;
  background:transparent!important;
  color:inherit;
  font:inherit;
  cursor:pointer;
  padding:6px 2px!important;
  box-shadow:none!important;
  backdrop-filter:none!important
}
.bar-track {
  height:155px;
  width:min(100%,38px);
  display:flex;
  align-items:end;
  border-bottom:1px solid currentColor
}
.bar-fill {
  display:block;
  width:100%;
  background:currentColor;
  opacity:.46;
  border-radius:4px 4px 0 0
}
.day-bar.selected .bar-fill,.day-bar:hover .bar-fill {
  opacity:.9
}
.day-bar.selected .bar-date {
  font-weight:700;
  text-decoration:underline;
  text-underline-offset:5px
}
.day-bar:focus-visible {
  outline:2px solid currentColor;
  outline-offset:-2px
}
.bar-date {
  font-size:calc(10px * var(--ui-font-scale,1));
  white-space:nowrap
}
.future {
  opacity:.45
}
.day-detail {
  font-size:calc(13px * var(--ui-font-scale,1));
  line-height:1.8;
  margin:12px 0 0
}
.statistics-details {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:20px;
  margin:20px 0
}
.breakdown {
  list-style:none;
  padding:0;
  margin:22px 0 0
}
.breakdown li {
  margin:0 0 22px
}
.breakdown-label {
  display:flex;
  justify-content:space-between;
  gap:12px;
  font-size:calc(13px * var(--ui-font-scale,1))
}
.breakdown strong {
  font-weight:500;
  font-variant-numeric:tabular-nums
}
.breakdown p {
  font-size:calc(11px * var(--ui-font-scale,1));
  margin:6px 0 0
}
.meter {
  height:6px;
  background:rgba(127,127,127,.16);
  margin-top:10px;
  border-radius:4px;
  overflow:hidden
}
.meter span {
  display:block;
  height:100%;
  background:currentColor;
  opacity:.65
}
.overdue {
  margin:28px 0 6px
}
.statistics-details p,.statistics-details a {
  font-size:calc(12px * var(--ui-font-scale,1));
  line-height:1.7
}
.statistics-details a {
  text-underline-offset:4px
}
.statistics-rules {
  font-size:calc(12px * var(--ui-font-scale,1));
  line-height:1.9
}
.statistics-rules summary {
  cursor:pointer
}
.table-scroll {
  overflow:auto;
  max-height:360px;
  margin:18px 0
}
table {
  width:100%;
  border-collapse:collapse;
  font-variant-numeric:tabular-nums
}
th,td {
  padding:9px 12px;
  text-align:left;
  border-bottom:1px solid rgba(127,127,127,.2)
}
caption {
  text-align:left;
  padding:8px 12px
}
.updated {
  font-size:calc(11px * var(--ui-font-scale,1));
  margin:22px 0
}
@media(max-width:1100px) {
  .statistics-cards {
    grid-template-columns:repeat(2,minmax(0,1fr))
  }
}
@media(max-width:700px) {
  .statistics-details {
    grid-template-columns:1fr
  }
  .range-controls label {
    flex:1;
    min-width:125px
  }
  .range-controls input {
    width:100%;
    box-sizing:border-box
  }
  .summary,.focus-trend,.statistics-details>.panel {
    padding:18px!important
  }
  .summary strong {
    font-size:calc(22px * var(--ui-font-scale,1))
  }
}
</style>
