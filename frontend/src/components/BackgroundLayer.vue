<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAppearance } from '../stores/appearance'
const appearance = useAppearance()
const { backgroundUrl, posterUrl, backgroundKind, paused, playbackBlocked, playbackAttempt } = appearance
const video = ref<HTMLVideoElement | null>(null)
const visible = ref(!document.hidden)
let disposed = false
const image = computed(() => backgroundKind.value === 'video' || (backgroundKind.value === 'gif' && paused.value) ? posterUrl.value : backgroundUrl.value)
async function syncPlayback() {
  await nextTick()
  const element = video.value
  if (!element || disposed) return
  if (paused.value || !visible.value) { element.pause(); return }
  element.muted = true
  try { await element.play() } catch { if (!disposed && element === video.value && !paused.value && visible.value) appearance.reportPlaybackBlocked() }
}
function visibility() { visible.value = !document.hidden; void syncPlayback() }
function mediaError(event: Event) { if (event.target === video.value) appearance.reportPlaybackBlocked() }
watch([backgroundUrl, paused, playbackAttempt], () => { void syncPlayback() }, { flush: 'post' })
onMounted(() => { void syncPlayback(); document.addEventListener('visibilitychange', visibility) })
onUnmounted(() => { disposed = true; video.value?.pause(); document.removeEventListener('visibilitychange', visibility) })
</script>

<template>
  <div class="workspace-background" aria-hidden="true" :style="image ? { backgroundImage: `url('${image}')` } : {}">
    <video v-if="backgroundKind === 'video' && backgroundUrl" ref="video" :key="backgroundUrl" class="background-video" :src="backgroundUrl" :poster="posterUrl || undefined" muted loop playsinline preload="auto" :style="{ visibility: playbackBlocked ? 'hidden' : 'visible' }" @error="mediaError" @loadeddata="syncPlayback"></video>
  </div>
</template>

<style scoped>
.background-video{width:100%;height:100%;object-fit:cover;object-position:center;pointer-events:none}
</style>
