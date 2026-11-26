<script setup lang="ts">
import { computed, ref } from 'vue'
import { useReminders } from '../stores/reminders'
import TimerSoundControl from './TimerSoundControl.vue'
const reminders = useReminders()
const supported = 'Notification' in window
const permission = ref(supported ? Notification.permission : 'denied')
const systemLabel = computed(() => !supported ? '此浏览器不支持系统通知' : permission.value === 'denied' ? '通知被浏览器阻止，请在网站权限中调整' : permission.value === 'granted' ? '系统通知权限已允许' : '尚未授权系统通知')
async function enable() { await reminders.enableSystem(); permission.value = Notification.permission }
</script>
<template>
  <section class="panel reminder-settings"><h2>日程与计时提醒</h2><p class="muted">开始和结束时显示站内提示；可额外启用声音和系统通知。</p>
    <TimerSoundControl />
    <label><input v-model="reminders.preferences.value.sound" type="checkbox" @change="reminders.save">其他日程 / 开始提示音</label><button type="button" class="quiet" @click="reminders.enableSound">启用 / 试听其他提示音</button>
    <label><input v-model="reminders.preferences.value.system" type="checkbox" :disabled="permission !== 'granted'" @change="reminders.save">系统通知</label><button type="button" class="quiet" :disabled="!supported || permission === 'denied'" @click="enable">授权系统通知</button><p class="muted">{{ systemLabel }}</p>
    <p v-if="!reminders.storageAvailable.value" class="form-error">本机存储不可用，提醒偏好或跨标签页去重可能无法保留。</p><p class="muted">提醒需要网站仍在浏览器中运行。关闭浏览器、电脑休眠或后台页面被挂起时，无法保证准时提醒；恢复后会同步状态，不集中补发旧提醒。选项保存在当前浏览器，并按账号区分。</p>
  </section>
</template>
<style scoped>
label{display:flex;gap:10px;align-items:center;margin:20px 0 10px;font-size:calc(14px * var(--ui-font-scale,1))}input{width:auto}.quiet{background:transparent;color:inherit;border:1px solid currentColor;padding:8px 12px;border-radius:6px;cursor:pointer;font:inherit;font-size:calc(13px * var(--ui-font-scale,1))}.reminder-settings{margin-top:24px}
</style>
