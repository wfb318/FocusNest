<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../api/client'
import AppearanceSettings from '../components/AppearanceSettings.vue'
import ReminderSettings from '../components/ReminderSettings.vue'
import JournalStorageSettings from '../components/JournalStorageSettings.vue'

const auth = useAuthStore()
const form = reactive({ nickname: auth.user?.nickname || '', avatar_url: auth.user?.avatar_url || '', timezone: auth.user?.timezone || 'Asia/Shanghai' })
const busy = ref(false)
const error = ref('')
const saved = ref(false)
async function save() {
  busy.value = true; error.value = ''; saved.value = false
  try {
    await auth.saveProfile({ nickname: form.nickname.trim() || null, avatar_url: form.avatar_url.trim() || null, timezone: form.timezone })
    saved.value = true
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <span class="eyebrow">WORKSPACE SETTINGS</span><h1>设置</h1>
  <JournalStorageSettings />
  <div class="settings-grid">
  <AppearanceSettings />
  <section class="panel profile-panel">
    <h2>个人资料</h2><p class="muted">管理你的显示名称与所在时区。</p>
    <div class="status-row"><span>用户名</span><span>{{ auth.user?.username }}</span></div>
    <div class="status-row"><span>邮箱</span><span>{{ auth.user?.email }}</span></div>
    <form @submit.prevent="save">
      <label for="nickname">昵称</label><input id="nickname" v-model="form.nickname" :disabled="busy" maxlength="64" placeholder="你希望我们如何称呼你">
      <label for="timezone">时区</label><input id="timezone" v-model="form.timezone" :disabled="busy" required maxlength="64" list="timezones" placeholder="Asia/Shanghai"><datalist id="timezones"><option value="Asia/Shanghai"/><option value="Asia/Tokyo"/><option value="Europe/London"/><option value="America/New_York"/><option value="UTC"/></datalist>
      <label for="avatar">头像链接（可选）</label><input id="avatar" v-model="form.avatar_url" :disabled="busy" type="url" maxlength="2048" placeholder="https://...">
      <p class="muted">当前保存链接，后续头像展示功能会使用此设置。</p>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p><p v-if="saved" role="status" class="form-success">个人资料已保存。</p>
      <button class="primary-button" type="submit" :disabled="busy">{{ busy ? '保存中…' : '保存资料' }}</button>
    </form>
  </section>
  </div>
  <ReminderSettings />
</template>

<style scoped>
.settings-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;align-items:start}.settings-grid .profile-panel{max-width:none}@media(max-width:1100px){.settings-grid{grid-template-columns:1fr}}
</style>
