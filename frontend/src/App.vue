<script setup lang="ts">
import { useAppearance } from './stores/appearance'
import BackgroundLayer from './components/BackgroundLayer.vue'
import { watchEffect } from 'vue'
import { styleVariables } from './utils/appearanceStyle'
const { stylePreferences } = useAppearance()
watchEffect(() => {
  for (const [key, value] of Object.entries(styleVariables(stylePreferences.value))) {
    document.documentElement.style.setProperty(key, value)
  }
})
const { veil, initialize } = useAppearance()
void initialize()
</script>

<template>
  <BackgroundLayer />
  <div class="workspace-veil" aria-hidden="true" :style="{ opacity: veil }"></div>
  <RouterView />
</template>
