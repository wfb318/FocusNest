import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from './auth'
import { useReminders } from './reminders'
import { currentFocus } from '../api/focus'
import { carryScheduleTemplate, listSchedule, startOccurrence } from '../api/schedules'
import { errorMessage } from '../api/client'
import { addDays, dateInZone, weekStart } from '../utils/scheduleTime'
import type { FocusSession } from '../types/focus'
import type { Occurrence } from '../types/schedule'

export const useWorkspaceRuntime = defineStore('workspace-runtime', () => {
  const auth = useAuthStore(), reminders = useReminders()
  const current = ref<FocusSession | null>(null), occurrences = ref<Occurrence[]>([])
  const settledOccurrences = ref<string[]>([])
  const now = ref(Date.now()), error = ref(''), conflict = ref(''), ready = ref(false)
  const collapsed = ref(false), mutating = ref(false)
  let anchor = Date.now(), anchorAt = performance.now()
  let tick: ReturnType<typeof setInterval> | undefined, poll: ReturnType<typeof setInterval> | undefined
  let pending: Promise<void> | undefined, generation = 0, active = false, lastScan = Date.now(), lastSuccess = 0
  const attempted = new Set<string>()
  let carriedWeek = ''
  let pendingCarry: Promise<void> | undefined
  async function prepareSchedules() {
    if (!auth.user) return
    const key = `${auth.user.timezone}:${weekStart(dateInZone(now.value, auth.user.timezone))}`
    if (carriedWeek === key) return
    if (pendingCarry) return pendingCarry
    const version = generation
    const request = carryScheduleTemplate().then(() => {
      if (version === generation) carriedWeek = key
    }).finally(() => { if (pendingCarry === request) pendingCarry = undefined })
    pendingCarry = request
    return request
  }
  const byStart = (a: Occurrence, b: Occurrence) => Date.parse(a.starts_at!) - Date.parse(b.starts_at!) || a.key.localeCompare(b.key)
  const currentSchedules = computed(() => occurrences.value.filter(item => !item.skipped && !item.time_warning && Date.parse(item.starts_at!) <= now.value && now.value < Date.parse(item.ends_at!)).sort(byStart))
  const nextSchedule = computed(() => occurrences.value.filter(item => !item.skipped && !item.time_warning && Date.parse(item.starts_at!) > now.value).sort(byStart)[0])
  const elapsed = computed(() => {
    const item = current.value
    if (!item) return 0
    if (item.mode === 'scheduled') return Math.max(0, (Math.min(now.value, Date.parse(item.window_end!)) - Date.parse(item.started_at)) / 1000)
    const value = item.elapsed_seconds + (item.status === 'running' ? Math.max(0, now.value - Date.parse(item.server_now)) / 1000 : 0)
    return item.duration_seconds ? Math.min(value, item.duration_seconds) : value
  })
  const waiting = computed(() => current.value?.mode === 'scheduled' && now.value < Date.parse(current.value.window_start!))
  const displaySeconds = computed(() => {
    const item = current.value
    if (!item) return 0
    if (item.mode === 'scheduled') return Math.max(0, (Date.parse(waiting.value ? item.window_start! : item.window_end!) - now.value) / 1000)
    return item.duration_seconds ? Math.max(0, item.duration_seconds - elapsed.value) : Math.floor(elapsed.value)
  })
  function apply(value: FocusSession | null) {
    if (value?.occurrence_key && ['completed', 'cancelled'].includes(value.status) && !settledOccurrences.value.includes(value.occurrence_key)) settledOccurrences.value.push(value.occurrence_key)
    current.value = value && ['scheduled', 'running', 'paused'].includes(value.status) ? value : null
    if (value) { anchor = Date.parse(value.server_now); anchorAt = performance.now(); now.value = anchor }
  }
  function scan() {
    now.value = anchor + performance.now() - anchorAt
    if (!active || !ready.value || performance.now() - lastSuccess > 30000) return
    const previous = Math.max(lastScan, now.value - 120000)
    for (const item of occurrences.value) {
      if (item.skipped || item.time_warning) continue
      for (const boundary of ['start', 'end'] as const) {
        const at = Date.parse(boundary === 'start' ? item.starts_at! : item.ends_at!)
        if (item[boundary === 'start' ? 'remind_start' : 'remind_end'] && previous < at && at <= now.value) {
          void reminders.notify(`schedule:${item.key}:${boundary}`, `${item.title}：${boundary === 'start' ? '日程开始' : '日程结束'}`)
        }
      }
    }
    const timer = current.value
    if (timer && !timer.occurrence_key) {
      if (timer.mode === 'scheduled') {
        const start = Date.parse(timer.window_start!), end = Date.parse(timer.window_end!)
        if (previous < start && start <= now.value) void reminders.notify(`timer:${timer.id}:start`, `${timer.title || '定时专注'}：计时开始`)
        if (previous < end && end <= now.value) void reminders.notify(`timer:${timer.id}:end`, `${timer.title || '定时专注'}：计时结束`)
      } else if (timer.duration_seconds && timer.status === 'running' && displaySeconds.value <= 0) {
        void reminders.notify(`timer:${timer.id}:end`, `${timer.title || '专注'}：计时结束`)
      }
    }
    lastScan = now.value
  }
  async function sync() {
    if (!active || !auth.user || mutating.value) return
    if (pending) return pending
    const version = generation
    const run = async () => {
      try {
        const today = dateInZone(now.value, auth.user!.timezone)
        const carry = prepareSchedules()
        if (carry) await carry
        if (version !== generation || !active) return
        const [timer, schedule] = await Promise.all([currentFocus(), listSchedule(addDays(today, -2), addDays(today, 8))])
        if (version !== generation || !active) return
        // Scan the old timer before a completed session disappears from /current.
        scan()
        apply(timer); anchor = Date.parse(schedule.server_now); anchorAt = performance.now(); now.value = anchor
        occurrences.value = schedule.items
        lastSuccess = performance.now()
        if (!ready.value) lastScan = now.value - 1000
        ready.value = true; error.value = ''
        scan()
        const due = currentSchedules.value.filter(item => item.timer_enabled)
        conflict.value = current.value && due.some(item => item.key !== current.value?.occurrence_key) ? '日程已到点，但已有活动计时。请先到专注页处理当前计时，再启动日程。' : ''
        if (!current.value) {
          const item = due.find(item => !attempted.has(item.key))
          if (item) {
            // Backend is authoritative; unique occurrence key makes repeated tabs/reloads safe.
            const started = await startOccurrence(item.schedule_id, item.occurrence_date)
            if (version !== generation || !active) return
            attempted.add(item.key); apply(started)
          }
        }
      } catch (cause) { if (version === generation && active) error.value = errorMessage(cause) }
    }
    pending = run().finally(() => { pending = undefined })
    return pending
  }
  async function activateOccurrence(item: Occurrence) {
    try { await mutate(() => startOccurrence(item.schedule_id, item.occurrence_date)); attempted.add(item.key); error.value = '' }
    catch (cause) { error.value = errorMessage(cause) }
    await sync()
  }
  async function mutate(operation: () => Promise<FocusSession>): Promise<FocusSession> {
    if (mutating.value) throw new Error('计时操作正在处理中，请稍后重试。')
    mutating.value = true
    const version = generation
    try {
      if (pending) await pending
      if (!active || version !== generation) throw new Error('登录状态已变化，请重新打开页面。')
      const value = await operation()
      if (active && version === generation) {
        if (current.value?.id === value.id && value.status === 'completed') {
          const event = value.occurrence_key && value.window_end && value.ended_at && Date.parse(value.ended_at) >= Date.parse(value.window_end)
            ? `schedule:${value.occurrence_key}:end` : `timer:${value.id}:end`
          void reminders.notify(event, `${value.title || '专注'}：计时结束`)
        }
        apply(value)
      }
      return value
    } finally { mutating.value = false }
  }
  function visible() { void sync() }
  function start() {
    if (active) return
    active = true; ++generation; attempted.clear(); ready.value = false
    anchor = Date.now(); anchorAt = performance.now(); now.value = anchor; lastScan = anchor
    reminders.configure(auth.user?.id || '')
    collapsed.value = window.innerWidth <= 1450
    try { const saved = localStorage.getItem('focusnest-runtime-collapsed'); if (saved !== null) collapsed.value = saved === 'true' } catch { /* Optional preference. */ }
    void sync(); tick = setInterval(scan, 250); poll = setInterval(() => { void sync() }, 5000)
    document.addEventListener('visibilitychange', visible); window.addEventListener('online', visible)
  }
  function stop() {
    active = false; ++generation; clearInterval(tick); clearInterval(poll)
    carriedWeek = ''; pendingCarry = undefined
    document.removeEventListener('visibilitychange', visible); window.removeEventListener('online', visible)
    current.value = null; occurrences.value = []; settledOccurrences.value = []; ready.value = false; error.value = ''; conflict.value = ''
    reminders.configure('')
  }
  function toggle() { collapsed.value = !collapsed.value; try { localStorage.setItem('focusnest-runtime-collapsed', String(collapsed.value)) } catch { /* Optional preference. */ } }
  return { current, occurrences, settledOccurrences, now, error, conflict, ready, collapsed, mutating, elapsed, waiting, displaySeconds, currentSchedules, nextSchedule, sync, prepareSchedules, apply, start, stop, toggle, activateOccurrence, mutate }
})
