<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getScheduleTemplateReview } from '../api/schedules'
import { useAuthStore } from '../stores/auth'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import type { ScheduleTemplateReview } from '../types/schedule'
import { dateInZone } from '../utils/scheduleTime'

const auth = useAuthStore(), runtime = useWorkspaceRuntime()
const review = ref<ScheduleTemplateReview | null>(null)
const day = computed(() => dateInZone(runtime.now, auth.user?.timezone || 'Asia/Shanghai'))
let request = 0
let timer: ReturnType<typeof setInterval> | undefined
async function check() {
  const version = ++request
  if (new Date(`${day.value}T12:00:00Z`).getUTCDay() !== 0) {
    review.value = null
    return
  }
  try {
    await runtime.prepareSchedules()
    const result = await getScheduleTemplateReview()
    if (version === request) review.value = result
  } catch { /* Try again when the page regains focus or at the next check. */ }
}
watch(day, check, { immediate: true })
onMounted(() => {
  window.addEventListener('focus', check)
  window.addEventListener('focusnest-schedule-review', check)
  timer = setInterval(check, 60_000)
})
onUnmounted(() => {
  request++
  clearInterval(timer)
  window.removeEventListener('focus', check)
  window.removeEventListener('focusnest-schedule-review', check)
})
</script>

<template>
  <aside v-if="review" class="panel template-reminder" aria-label="下周日程提醒">
    <span>下周从 {{ review.week_start }} 开始。要沿用本周模板，还是换一个？</span>
    <RouterLink :to="{ name: 'schedule', query: { review: review.week_start } }">确认下周日程 →</RouterLink>
  </aside>
</template>

<style scoped>
.template-reminder{display:flex;align-items:center;justify-content:space-between;gap:12px 24px;flex-wrap:wrap;padding:14px 18px!important;margin:0 0 20px}
.template-reminder a{color:inherit;text-decoration:underline;text-underline-offset:4px}
</style>
