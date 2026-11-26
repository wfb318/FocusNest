<script setup lang="ts">
import { useReminders } from '../stores/reminders'
const reminders = useReminders()
</script>
<template>
  <div class="timer-sound-control">
    <label><input v-model="reminders.preferences.value.endSound" type="checkbox" @change="reminders.save">计时结束提示音</label>
    <button type="button" class="quiet" @click="reminders.testEndSound">试听结束提示音</button>
    <span class="muted">{{ !reminders.preferences.value.endSound ? '已关闭' : reminders.audioReady.value ? '声音已就绪 · 结束时播放三声铃音' : '默认开启，点击试听或开始计时以准备声音' }}</span>
  </div>
</template>
<style scoped>
.timer-sound-control{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:18px 0;font-size:calc(13px * var(--ui-font-scale,1))}.timer-sound-control label{display:flex;align-items:center;gap:8px;margin:0;font:inherit}.timer-sound-control input{width:auto}.timer-sound-control .muted{font-size:calc(12px * var(--ui-font-scale,1))}.quiet{padding:8px 12px;background:transparent;color:inherit;border:1px solid currentColor;border-radius:7px;font:inherit;cursor:pointer}
</style>
