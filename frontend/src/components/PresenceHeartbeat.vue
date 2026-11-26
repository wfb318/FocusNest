<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { sendHeartbeat } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { createPresenceReporter } from '../utils/presence'

const auth = useAuthStore()
const owner = auth.user?.id
const reporter = createPresenceReporter({
  active: () => Boolean(owner && auth.user?.id === owner && document.visibilityState === 'visible'),
  send: sendHeartbeat,
})
let timer: ReturnType<typeof setInterval> | undefined
const tick = () => { void reporter.tick() }

onMounted(() => {
  tick()
  timer = setInterval(tick, 60_000)
  document.addEventListener('visibilitychange', tick)
  window.addEventListener('online', tick)
})
onUnmounted(() => {
  reporter.stop()
  clearInterval(timer)
  document.removeEventListener('visibilitychange', tick)
  window.removeEventListener('online', tick)
})
</script>

<template><span hidden aria-hidden="true"></span></template>
