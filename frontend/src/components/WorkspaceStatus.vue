<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { useReminders } from '../stores/reminders'
import { minuteLabel, secondsLabel } from '../utils/scheduleTime'
const runtime = useWorkspaceRuntime(), reminders = useReminders(), route = useRoute()
const modes = { scheduled: '定时专注', pomodoro: '番茄钟', countdown: '倒计时', stopwatch: '正计时' }
const showTimer = computed(() => route.name !== 'focus' && runtime.current)
</script>
<template>
  <aside class="workspace-status" :class="{ collapsed: runtime.collapsed }" aria-label="当前日程与计时">
    <button class="status-toggle" :aria-expanded="!runtime.collapsed" @click="runtime.toggle()">{{ runtime.collapsed ? '展开日程与计时' : '收起日程与计时' }}</button>
    <div v-if="!runtime.collapsed" class="status-content">
      <header><span class="eyebrow">RIGHT NOW</span><h2>此刻的安排</h2></header>
      <div v-if="!runtime.ready && !runtime.error" class="muted">正在同步…</div>
      <section v-for="item in runtime.currentSchedules" :key="item.key" class="panel status-card"><span class="small-label">当前日程</span><h3>{{ item.title }}</h3><p>{{ minuteLabel(item.start_minute) }}–{{ minuteLabel(item.end_minute) }} · {{ item.timezone }}</p><strong class="status-clock">{{ secondsLabel((Date.parse(item.ends_at!) - runtime.now) / 1000) }}</strong><p class="muted">距离日程结束</p><p v-if="runtime.current?.occurrence_key === item.key" class="muted">{{ route.name === 'focus' ? '已在专注页显示计时' : '已关联下方计时' }}</p><p v-else-if="runtime.settledOccurrences.includes(item.key)" class="muted">本次计时已结束</p><button v-else-if="item.timer_enabled" class="quiet" :disabled="!!runtime.current || runtime.mutating" @click="runtime.activateOccurrence(item)">启动本次计时</button></section>
      <p v-if="runtime.ready && !runtime.currentSchedules.length" class="muted">现在没有日程，按自己的节奏来。</p>
      <section v-if="showTimer && runtime.current" class="panel status-card"><span class="small-label">{{ modes[runtime.current.mode] }}{{ runtime.current.status === 'paused' ? ' · 已暂停' : '' }}</span><h3>{{ runtime.current.title || (runtime.current.kind === 'break' ? '休息' : '专注计时') }}</h3><strong class="status-clock" role="timer">{{ secondsLabel(runtime.displaySeconds) }}</strong><p class="muted">{{ runtime.waiting ? '距离开始' : runtime.current.mode === 'stopwatch' ? '已用时间' : '剩余时间' }}</p><RouterLink to="/focus">前往专注页管理 →</RouterLink></section>
      <section v-if="runtime.nextSchedule" class="status-next"><span class="small-label">下一项日程</span><h3>{{ runtime.nextSchedule.title }}</h3><p>{{ runtime.nextSchedule.occurrence_date.slice(5) }} {{ minuteLabel(runtime.nextSchedule.start_minute) }} · {{ runtime.nextSchedule.timezone }}</p></section>
      <p v-if="runtime.conflict" class="form-error" role="status">{{ runtime.conflict }}</p>
      <p v-if="runtime.error" class="form-error" role="alert">{{ runtime.error }} 显示可能已过期。<button class="quiet" @click="runtime.sync">重新同步</button></p>
      <RouterLink to="/schedule" class="status-link">查看每周日程 →</RouterLink>
    </div>
  </aside>
  <div class="workspace-notices" aria-live="polite" aria-atomic="false"><div v-for="message in reminders.messages.value" :key="message.id" class="panel workspace-notice"><span>{{ message.text }}</span><button :aria-label="`关闭提示：${message.text}`" @click="reminders.dismiss(message.id)">×</button></div></div>
</template>
<style scoped>
.workspace-status{width:260px;flex:0 0 260px;align-self:flex-start;position:sticky;top:24px;margin:36px 22px 24px 0;max-height:calc(100vh - 48px);overflow:auto;overflow-wrap:anywhere}.workspace-status.collapsed{width:44px;flex-basis:44px}.status-toggle{font:inherit;font-size:calc(12px * var(--ui-font-scale,1));padding:10px 3px;background:transparent;border:0;color:inherit;cursor:pointer;text-align:left}.collapsed .status-toggle{writing-mode:vertical-rl}.status-content{padding-top:16px}.status-card{padding:18px!important;margin:14px 0}.status-card h3,.status-next h3{font-size:calc(15px * var(--ui-font-scale,1));line-height:1.6;margin:12px 0}.status-card p{margin:8px 0}.status-card p,.status-next p,.status-link{font-size:calc(12px * var(--ui-font-scale,1));line-height:1.8}.status-clock{font-size:calc(26px * var(--ui-font-scale,1));font-weight:500;font-variant-numeric:tabular-nums}.status-card a{font-size:calc(12px * var(--ui-font-scale,1));text-decoration:underline}.status-next{padding:18px 3px}.status-link{display:block;margin:14px 0}.quiet{background:transparent;color:inherit;border:1px solid currentColor;padding:6px;cursor:pointer}.workspace-notices{position:fixed;z-index:90;bottom:24px;right:24px;width:min(400px,calc(100vw - 48px));display:grid;gap:10px}.workspace-notice{display:flex;justify-content:space-between;gap:16px;padding:18px!important;background:rgba(var(--glass-rgb),.75)!important}.workspace-notice button{background:transparent;border:0;color:inherit;font:inherit;cursor:pointer}@media(max-width:1450px){.workspace-status{position:fixed;right:16px;bottom:16px;top:auto;margin:0;z-index:40;max-height:80vh;width:280px;background:rgba(var(--glass-rgb),.8);backdrop-filter:blur(2px);padding:12px;border:1px solid var(--glass-border);border-radius:12px}.workspace-status.collapsed{width:auto;max-width:220px}.collapsed .status-toggle{writing-mode:horizontal-tb}.workspace-notices{bottom:90px}}@media(max-width:720px){.workspace-status{max-width:calc(100vw - 32px)}}
</style>
