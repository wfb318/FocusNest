<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../api/client'
import WorkspaceStatus from '../components/WorkspaceStatus.vue'
import ScheduleTemplateReminder from '../components/ScheduleTemplateReminder.vue'
import PresenceHeartbeat from '../components/PresenceHeartbeat.vue'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { confirmJournalLeave } from '../services/journalDraftGuard'

const upcoming = ['AI 助手']
const auth = useAuthStore()
const router = useRouter()
const runtime = useWorkspaceRuntime()
watch(() => auth.user?.id, id => { runtime.stop(); if (id) runtime.start() }, { immediate: true })
onUnmounted(() => runtime.stop())
const error = ref('')
const busy = ref(false)
watch(() => auth.user, user => { if (!user) void router.replace('/login') })
async function logout() {
  if (!(await confirmJournalLeave())) return
  busy.value = true; error.value = ''
  try { await auth.logout(); await router.replace('/login') }
  catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <div v-if="auth.user" class="workspace">
    <aside class="sidebar">
      <RouterLink to="/" class="brand"><span class="brand-mark">F</span> FocusNest</RouterLink>
      <p class="nav-label">个人工作台</p>
      <nav aria-label="主导航">
        <RouterLink to="/" class="nav-link" exact-active-class="active">工作台</RouterLink>
        <RouterLink to="/tasks" class="nav-link" active-class="active">任务</RouterLink>
        <RouterLink to="/focus" class="nav-link" active-class="active">专注</RouterLink>
        <RouterLink to="/schedule" class="nav-link" active-class="active">日程</RouterLink>
        <RouterLink to="/statistics" class="nav-link" active-class="active">统计</RouterLink>
        <RouterLink to="/journals" class="nav-link" active-class="active">日记</RouterLink>
        <RouterLink to="/notes" class="nav-link" active-class="active">笔记</RouterLink>
        <RouterLink to="/problems" class="nav-link" active-class="active">问题备忘</RouterLink>
        <RouterLink to="/documents" class="nav-link" active-class="active">文档</RouterLink>
        <RouterLink v-if="auth.user.role === 'admin'" to="/admin" class="nav-link" active-class="active">管理后台</RouterLink>
        <div v-for="item in upcoming" :key="item" class="nav-disabled" aria-disabled="true">{{ item }} <span>待开发</span></div>
      </nav>
      <div class="sidebar-bottom">
        <RouterLink to="/settings" class="nav-link" active-class="active">设置与外观</RouterLink>
        <div class="account-name">{{ auth.user?.nickname || auth.user?.username }}</div>
        <button class="logout-button" :disabled="busy" @click="logout">{{ busy ? '退出中…' : '退出登录' }}</button>
        <div v-if="error" role="alert" class="form-error">{{ error }}</div>
      </div>
    </aside>
    <main class="main"><ScheduleTemplateReminder :key="auth.user.id" /><RouterView :key="auth.user.id" /></main>
    <WorkspaceStatus />
    <PresenceHeartbeat :key="auth.user.id" />
  </div>
</template>
