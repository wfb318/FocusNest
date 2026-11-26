<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { createProblem, editProblem, exportProblems, listProblems, setProblemStatus } from '../api/problems'
import type { Problem, ProblemBucket, ProblemPage } from '../api/problems'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { dateInZone } from '../utils/scheduleTime'

const auth = useAuthStore(), runtime = useWorkspaceRuntime()
const buckets: Record<ProblemBucket, string> = { today: '今日问题', history: '历史问题', resolved: '已解决', all: '全部' }
const bucket = ref<ProblemBucket>('today'), page = ref(1), query = ref(''), appliedQuery = ref('')
const data = ref<ProblemPage | null>(null), draft = ref(''), editing = ref<Problem | null>(null), editContent = ref('')
const busy = ref(false), loading = ref(false), error = ref(''), editError = ref(''), notice = ref('')
const editDialog = ref<HTMLDialogElement | null>(null), discardDialog = ref<HTMLDialogElement | null>(null)
const pages = computed(() => Math.max(1, Math.ceil((data.value?.total || 0) / 20)))
const dirty = computed(() => !!draft.value || (!!editing.value && editContent.value !== editing.value.content))
let disposed = false, version = 0, confirmDiscard: ((value: boolean) => void) | undefined
let poll: ReturnType<typeof setInterval> | undefined
function time(value: string) { return new Intl.DateTimeFormat('zh-CN', { timeZone: data.value?.timezone || auth.user?.timezone || 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function category(item: Problem) { return item.is_resolved ? '已解决' : dateInZone(Date.parse(item.created_at), data.value!.timezone) < data.value!.today ? '历史问题' : '今日问题' }
async function load() {
  if (disposed || busy.value) return
  const request = ++version; loading.value = true
  try {
    const result = await listProblems(bucket.value, appliedQuery.value, page.value)
    if (disposed || request !== version) return
    data.value = result; error.value = ''
    if (page.value > pages.value) { page.value = pages.value; await load() }
  } catch (cause) { if (!disposed && request === version) error.value = errorMessage(cause) }
  finally { if (request === version) loading.value = false }
}
function select(value: ProblemBucket) { if (busy.value) return; bucket.value = value; page.value = 1; void load() }
function search() { appliedQuery.value = query.value.trim(); page.value = 1; void load() }
async function add() {
  if (busy.value || loading.value || !draft.value.trim()) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await createProblem(draft.value); if (!disposed) { draft.value = ''; bucket.value = 'today'; query.value = ''; appliedQuery.value = ''; page.value = 1; notice.value = '问题已记录。' } }
  catch (cause) { if (!disposed) error.value = errorMessage(cause) }
  finally { busy.value = false }
  const actionError = error.value; await load(); if (actionError) error.value = actionError
}
async function toggle(item: Problem, event: Event) {
  (event.target as HTMLInputElement).checked = item.is_resolved
  if (busy.value || loading.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await setProblemStatus(item); if (!disposed) notice.value = item.is_resolved ? '已重新打开问题，按原记录日期归类。' : '已标记解决，并记录解决时间。' }
  catch (cause) { if (!disposed) error.value = errorMessage(cause) }
  finally { busy.value = false }
  const actionError = error.value; await load(); if (actionError) error.value = actionError
}
function edit(item: Problem) { editing.value = item; editContent.value = item.content; editError.value = ''; editDialog.value?.showModal() }
function closeEdit() { if (busy.value) return; editDialog.value?.close(); editing.value = null }
async function saveEdit() {
  if (!editing.value || busy.value || !editContent.value.trim()) return
  busy.value = true; editError.value = ''
  try { await editProblem(editing.value, editContent.value); editDialog.value?.close(); editing.value = null; notice.value = '问题内容已更新，原记录时间保留。' }
  catch (cause) { editError.value = errorMessage(cause) }
  finally { busy.value = false }
  await load()
}
async function download() {
  if (busy.value || loading.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const blob = await exportProblems(bucket.value, appliedQuery.value)
    if (disposed) return
    const url = URL.createObjectURL(blob), anchor = document.createElement('a')
    anchor.href = url; anchor.download = `FocusNest-问题备忘-${bucket.value}-${data.value?.today || 'export'}.md`
    document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    notice.value = 'Markdown 文档已生成，包含当前分类和搜索范围内的全部问题及时间。'
  } catch (cause) { if (!disposed) error.value = errorMessage(cause) }
  finally { busy.value = false }
}
function resolveDiscard(value: boolean) { discardDialog.value?.close(); confirmDiscard?.(value); confirmDiscard = undefined }
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
function visible() { if (document.visibilityState === 'visible' && !busy.value) void load() }
onBeforeRouteLeave(() => {
  if (!auth.user) return true
  if (busy.value) return false
  if (!dirty.value) return true
  return new Promise<boolean>(resolve => { confirmDiscard = resolve; discardDialog.value?.showModal() })
})
watch(() => data.value && dateInZone(runtime.now, auth.user?.timezone || data.value.timezone) !== data.value.today, changed => { if (changed) void load() })
onMounted(() => { void load(); poll = setInterval(visible, 60000); window.addEventListener('beforeunload', beforeUnload); window.addEventListener('online', visible); document.addEventListener('visibilitychange', visible) })
onUnmounted(() => { disposed = true; ++version; clearInterval(poll); resolveDiscard(false); window.removeEventListener('beforeunload', beforeUnload); window.removeEventListener('online', visible); document.removeEventListener('visibilitychange', visible) })
</script>
<template>
  <header class="page-header"><div><span class="eyebrow">ONE QUESTION AT A TIME</span><h1>问题备忘</h1><p class="muted">写下卡住的地方，让每个问题都有去处。</p></div><button class="quiet" :disabled="busy || loading || !data" @click="download">导出{{ buckets[bucket] }}（Markdown）</button></header>
  <section class="panel problem-composer" aria-label="记录新问题"><form @submit.prevent="add"><label for="new-problem">遇到了什么问题？</label><textarea id="new-problem" v-model="draft" maxlength="10000" rows="4" :disabled="busy" placeholder="记录现象、疑问或尝试过的办法…" required></textarea><div class="composer-actions"><span class="muted">{{ draft.length }} / 10000 · 点击记录后保存</span><button class="primary-button" :disabled="busy || loading || !draft.trim()">记录问题</button></div></form></section>
  <p class="muted">未解决的问题在次日自动归入历史，原记录时间保留；勾选后移入已解决并记录解决时间。{{ data?.timezone }}</p>
  <p v-if="error" class="form-error" role="alert">{{ error }}</p><p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  <div class="problem-toolbar"><nav aria-label="问题分类"><button v-for="(label, key) in buckets" :key="key" class="quiet" :class="{ selected: bucket === key }" :aria-current="bucket === key ? 'page' : undefined" :disabled="busy" @click="select(key)">{{ label }} <span v-if="data">{{ data.counts[key] }}</span></button></nav><form @submit.prevent="search"><label for="problem-query" class="sr-only">搜索问题</label><input id="problem-query" v-model="query" maxlength="100" placeholder="搜索问题内容" :disabled="busy"><button class="quiet" :disabled="busy">查询</button><button class="quiet" type="button" :disabled="busy || loading" @click="load">刷新</button></form></div>
  <p v-if="loading" class="muted" role="status">正在同步问题…</p>
  <ul v-if="data?.items.length" class="problem-list" :aria-label="buckets[bucket]"><li v-for="item in data.items" :key="item.id" class="panel problem-card"><input type="checkbox" :checked="item.is_resolved" :disabled="busy || loading" :aria-label="`${item.is_resolved ? '重新打开' : '解决问题'}：${item.content.slice(0, 50)}`" @change="toggle(item, $event)"><div class="problem-body"><p class="problem-content">{{ item.content }}</p><div class="problem-meta"><span>{{ category(item) }}</span><time :datetime="item.created_at">记录 {{ time(item.created_at) }}</time><time v-if="item.resolved_at" :datetime="item.resolved_at">解决 {{ time(item.resolved_at) }}</time><time v-if="item.updated_at !== item.created_at" :datetime="item.updated_at">更新 {{ time(item.updated_at) }}</time><button class="quiet" :disabled="busy || loading" @click="edit(item)">编辑</button></div></div></li></ul>
  <p v-else-if="!loading && data" class="panel muted">{{ appliedQuery ? '没有找到匹配的问题。' : bucket === 'today' ? '今天还没有待解决的问题，遇到疑问时记下来。' : bucket === 'history' ? '没有历史遗留问题。' : bucket === 'resolved' ? '解决的问题会出现在这里。' : '先记录你的第一个问题。' }}</p>
  <nav v-if="data" class="pagination" aria-label="问题分页"><span>共 {{ data.total }} 条 · {{ page }} / {{ pages }}</span><button class="quiet" :disabled="busy || loading || page <= 1" @click="page--; load()">上一页</button><button class="quiet" :disabled="busy || loading || page >= pages" @click="page++; load()">下一页</button></nav>
  <dialog ref="editDialog" aria-labelledby="problem-edit-title" @cancel.prevent="closeEdit"><h2 id="problem-edit-title">编辑问题</h2><form @submit.prevent="saveEdit"><label for="edit-problem">问题内容</label><textarea id="edit-problem" v-model="editContent" rows="8" maxlength="10000" :disabled="busy" required></textarea><p class="muted">保留最初记录日期。取消已解决的勾选会重新打开问题，并清除本次解决时间。</p><p v-if="editError" class="form-error" role="alert">{{ editError }}</p><div class="dialog-actions"><button class="primary-button" :disabled="busy || !editContent.trim()">保存修改</button><button class="quiet" type="button" :disabled="busy" @click="closeEdit">返回</button></div></form></dialog>
  <dialog ref="discardDialog" aria-labelledby="problem-discard-title" @cancel.prevent="resolveDiscard(false)"><h2 id="problem-discard-title">有尚未保存的问题</h2><p>离开将放弃当前输入。</p><div class="dialog-actions"><button class="quiet" @click="resolveDiscard(false)">继续记录</button><button class="quiet" @click="resolveDiscard(true)">放弃并离开</button></div></dialog>
</template>
<style scoped>
textarea{display:block;width:100%;min-height:110px;resize:vertical;padding:12px;border:1px solid rgba(127,127,127,.35);border-radius:8px;font-family:inherit;font-size:calc(14px * var(--ui-font-scale,1));line-height:1.8;color:var(--text-primary)}.problem-composer label{display:block;margin:0 0 12px}
h1{margin:12px 0}.quiet{padding:8px 12px;background:transparent;color:inherit;border:1px solid transparent;border-radius:7px;font:inherit;font-size:calc(13px * var(--ui-font-scale,1));cursor:pointer}.problem-composer{margin-top:22px}.composer-actions,.dialog-actions,.pagination{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:16px}.composer-actions{justify-content:space-between}.primary-button{width:auto;margin:0}.composer-actions .muted,.pagination{font-size:calc(12px * var(--ui-font-scale,1))}.problem-toolbar{display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap;margin:24px 0}.problem-toolbar nav,.problem-toolbar form{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.problem-toolbar input{width:210px;max-width:100%;padding:10px}.selected{font-weight:700;border-bottom:2px solid currentColor!important;border-radius:0}.problem-list{list-style:none;padding:0;display:grid;gap:14px}.problem-card{display:flex;align-items:flex-start;gap:16px;padding:20px!important}.problem-card>input{width:20px;height:20px;flex-shrink:0;margin-top:5px;accent-color:#39765c}.problem-body{min-width:0;flex:1}.problem-content{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;font-size:calc(15px * var(--ui-font-scale,1));margin:0 0 12px}.problem-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:calc(12px * var(--ui-font-scale,1));color:var(--text-muted)}.problem-meta .quiet{margin-left:auto}.pagination{justify-content:center;margin:24px 0}dialog{width:min(600px,calc(100vw - 32px));max-height:88vh;overflow:auto;padding:26px;border-radius:14px;color:var(--text-primary)}dialog textarea{width:100%;font:inherit}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:600px){.problem-toolbar form{width:100%}.problem-toolbar input{flex:1;min-width:100px}.problem-meta .quiet{margin-left:0}}
</style>
