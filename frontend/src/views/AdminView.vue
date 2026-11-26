<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getAdminOverview, getAdminUsers } from '../api/admin'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { AdminOverview, AdminUserPage, AdminUserQuery } from '../types/admin'

const auth = useAuthStore(), router = useRouter()
const overview = ref<AdminOverview | null>(null), records = ref<AdminUserPage | null>(null)
const loading = ref(false), error = ref('')
const form = reactive({ search: '', role: '', online: '', page_size: 20 })
const query = ref<AdminUserQuery>({ page: 1, page_size: 20, search: '' })
const pageCount = computed(() => Math.max(1, Math.ceil((records.value?.total || 0) / query.value.page_size)))
const zone = computed(() => overview.value?.timezone || auth.user?.timezone || 'Asia/Shanghai')
let disposed = false, version = 0
let timer: ReturnType<typeof setInterval> | undefined

function formatTime(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: zone.value, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}
async function load() {
  if (disposed || auth.user?.role !== 'admin') return
  const request = ++version, owner = auth.user.id
  const params = { ...query.value }
  loading.value = true; error.value = ''; overview.value = null; records.value = null
  try {
    const [summary, users] = await Promise.all([getAdminOverview(), getAdminUsers(params)])
    if (disposed || request !== version || auth.user?.id !== owner || auth.user.role !== 'admin') return
    const lastPage = Math.max(1, Math.ceil(users.total / params.page_size))
    if (params.page > lastPage) {
      query.value.page = lastPage
      await load()
      return
    }
    overview.value = summary; records.value = users
  } catch (cause) {
    if (disposed || request !== version || auth.user?.id !== owner) return
    error.value = errorMessage(cause)
    if (axios.isAxiosError(cause) && cause.response?.status === 403) {
      try { await auth.reloadProfile() } catch { /* Keep the permission error visible. */ }
    }
  } finally { if (request === version) loading.value = false }
}
function search() {
  query.value = {
    page: 1, page_size: form.page_size, search: form.search.trim(),
    role: form.role === 'admin' || form.role === 'user' ? form.role : undefined,
    online: form.online === '' ? undefined : form.online === 'true',
  }
  void load()
}
function turnPage(delta: number) {
  if (loading.value) return
  query.value.page += delta
  void load()
}
function visibleRefresh() {
  if (document.visibilityState === 'visible' && !loading.value) void load()
}
watch(() => auth.user?.role, role => {
  if (role !== 'admin') {
    ++version; overview.value = null; records.value = null
    void router.replace('/')
  }
})
onMounted(() => {
  void load()
  timer = setInterval(visibleRefresh, 60_000)
  document.addEventListener('visibilitychange', visibleRefresh)
  window.addEventListener('online', visibleRefresh)
})
onUnmounted(() => {
  disposed = true; ++version; overview.value = null; records.value = null
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visibleRefresh)
  window.removeEventListener('online', visibleRefresh)
})
</script>

<template>
  <header class="page-header">
    <div><p class="eyebrow">FOCUSNEST ADMIN</p><h1>管理后台</h1><p class="muted">查看账号与平台运行概况。</p></div>
    <button class="quiet" :disabled="loading" @click="load">{{ loading ? '更新中…' : '刷新数据' }}</button>
  </header>
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <p v-if="loading" class="muted" role="status">正在读取注册统计与用户列表…</p>
  <div v-if="overview" class="admin-summary">
    <section class="panel summary"><span>总注册人数</span><strong>{{ overview.registered_total }}</strong><p class="muted">含 {{ overview.administrators }} 个管理员账号</p></section>
    <section class="panel summary"><span>近期在线</span><strong>{{ overview.online_users }}</strong><p class="muted">最近 5 分钟 · 同一用户去重</p></section>
    <section class="panel summary"><span>今日新增</span><strong>{{ overview.registered_today }}</strong><p class="muted">{{ overview.today }} · {{ overview.timezone }}</p></section>
    <section class="panel summary"><span>本周 / 本月新增</span><strong>{{ overview.registered_week }} <small>/ {{ overview.registered_month }}</small></strong><p class="muted">本周从周一开始</p></section>
  </div>
  <section class="panel user-panel" aria-labelledby="admin-users-title">
    <div class="panel-heading"><h2 id="admin-users-title">用户列表</h2><span v-if="records" class="muted">符合条件 {{ records.total }} 人</span></div>
    <form class="admin-filters" aria-label="筛选用户" @submit.prevent="search">
      <label for="admin-search">搜索账号<input id="admin-search" v-model="form.search" maxlength="100" placeholder="用户名、邮箱或昵称"></label>
      <label for="admin-role">角色<select id="admin-role" v-model="form.role"><option value="">全部角色</option><option value="user">普通用户</option><option value="admin">管理员</option></select></label>
      <label for="admin-online">在线状态<select id="admin-online" v-model="form.online"><option value="">全部状态</option><option value="true">近期在线</option><option value="false">近期离线</option></select></label>
      <label for="admin-page-size">每页<select id="admin-page-size" v-model.number="form.page_size"><option :value="20">20 人</option><option :value="50">50 人</option><option :value="100">100 人</option></select></label>
      <button class="quiet" type="submit" :disabled="loading">查询</button>
    </form>
    <div v-if="records" class="table-scroll">
      <table>
        <caption class="visually-hidden">用户账号、角色、注册与活动时间</caption>
        <thead><tr><th scope="col">账号</th><th scope="col">邮箱</th><th scope="col">角色</th><th scope="col">状态</th><th scope="col">注册时间</th><th scope="col">最近登录</th><th scope="col">最近活动</th></tr></thead>
        <tbody><tr v-for="user in records.items" :key="user.id">
          <th scope="row"><span>{{ user.username }}</span><small v-if="user.nickname">{{ user.nickname }}</small></th>
          <td class="email-cell">{{ user.email }}</td><td>{{ user.role === 'admin' ? '管理员' : '普通用户' }}</td>
          <td><span class="presence-status" :class="{ online: user.online }">{{ user.online ? '在线' : '离线' }}</span></td>
          <td>{{ formatTime(user.created_at) }}</td><td>{{ formatTime(user.last_login_at) }}</td><td>{{ formatTime(user.last_seen_at) }}</td>
        </tr></tbody>
      </table>
      <p v-if="!records.items.length" class="muted empty">没有符合条件的用户。</p>
    </div>
    <nav v-if="records" class="pagination" aria-label="用户列表分页">
      <span>第 {{ query.page }} / {{ pageCount }} 页</span>
      <button class="quiet" :disabled="loading || query.page <= 1" @click="turnPage(-1)">上一页</button>
      <button class="quiet" :disabled="loading || query.page >= pageCount" @click="turnPage(1)">下一页</button>
    </nav>
  </section>
  <section class="admin-help">
    <p class="muted">近期在线按有效登录会话最近 5 分钟的活动统计。页面可见时约每分钟同步心跳；关闭页面或长时间切到后台后，人数会延迟变化。</p>
    <p class="muted">后台展示账号资料与统计。用户日记、笔记和文档正文保持原有访问权限，本地日记不会上传。</p>
    <p v-if="overview" class="muted">更新于 {{ formatTime(overview.server_now) }} · 时间按 {{ zone }} 显示 · 约每分钟刷新</p>
  </section>
</template>

<style scoped>
.quiet{padding:9px 13px;border-radius:8px;font:inherit;font-size:calc(13px * var(--ui-font-scale,1))}
.admin-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:26px 0}
.summary{padding:22px 24px;min-width:0}.summary>span{font-size:calc(13px * var(--ui-font-scale,1))}
.summary strong{display:block;font-size:calc(34px * var(--ui-font-scale,1));font-weight:550;margin:10px 0}
.summary small{font-size:.65em;font-weight:400}.summary p{margin:0;font-size:calc(12px * var(--ui-font-scale,1))}
.user-panel{margin-top:24px;min-width:0}.admin-filters{display:flex;align-items:end;flex-wrap:wrap;gap:14px;margin:12px 0 24px}
.admin-filters label{display:grid;gap:7px;margin:0;font-size:calc(13px * var(--ui-font-scale,1))}
.admin-filters input,.admin-filters select{width:auto;margin:0;padding:9px 12px;border-radius:8px;font:inherit}
.admin-filters input{width:240px;max-width:100%}.admin-filters button{margin-bottom:1px}
.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:calc(13px * var(--ui-font-scale,1))}
th,td{text-align:left;padding:14px 12px;border-bottom:1px solid var(--glass-border,#e0e5dc);white-space:nowrap;vertical-align:middle}
thead th{font-weight:500}tbody th{font-weight:500}tbody th small{display:block;font-size:.9em;margin-top:5px;opacity:.7}
.email-cell{max-width:260px;overflow:hidden;text-overflow:ellipsis}.presence-status{display:inline-flex;align-items:center;gap:6px}
.presence-status::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor;opacity:.25}.presence-status.online::before{opacity:1;background:#39765c}
.pagination{display:flex;align-items:center;justify-content:flex-end;gap:12px;margin-top:22px;font-size:calc(13px * var(--ui-font-scale,1))}
.pagination span{margin-right:auto}.empty{padding:18px 12px}.admin-help{margin-top:22px}.admin-help p{margin:7px 0;font-size:calc(12px * var(--ui-font-scale,1))}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
@media(max-width:1200px){.admin-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.admin-summary{grid-template-columns:1fr;gap:10px}.summary strong{font-size:calc(28px * var(--ui-font-scale,1))}.admin-filters{display:grid;grid-template-columns:1fr 1fr}.admin-filters label:first-child{grid-column:1/-1}.admin-filters input{width:100%}.user-panel{padding:18px}.pagination{flex-wrap:wrap}}
</style>
