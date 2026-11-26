<script setup lang="ts">
import { computed, onUnmounted, ref, useId, watch } from 'vue'
import { getProblem, listProblems } from '../api/problems'
import type { Problem, ProblemBucket } from '../api/problems'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useWorkspaceRuntime } from '../stores/workspaceRuntime'
import { dateInZone } from '../utils/scheduleTime'

const props = defineProps<{ modelValue: string | null; readonly: boolean; disabled: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()
const auth = useAuthStore(), runtime = useWorkspaceRuntime(), id = useId()
const bucket = ref<ProblemBucket>('all'), query = ref(''), appliedQuery = ref('')
const options = ref<Problem[]>([]), selected = ref<Problem | null>(null)
const page = ref(1), total = ref(0), loading = ref(false), detailLoading = ref(false), error = ref(''), detailError = ref('')
const labels: Record<ProblemBucket, string> = { all: '全部问题', today: '今日问题', history: '历史问题', resolved: '已解决' }
let disposed = false, listVersion = 0, detailVersion = 0
const selectedOutside = computed(() => props.modelValue && !options.value.some(item => item.id === props.modelValue))
const category = computed(() => {
  if (!selected.value) return ''
  if (selected.value.is_resolved) return '已解决'
  const zone = auth.user?.timezone || 'Asia/Shanghai'
  return dateInZone(Date.parse(selected.value.created_at), zone) < dateInZone(runtime.now, zone) ? '历史问题' : '今日问题'
})
function time(value: string) { return new Date(value).toLocaleString('zh-CN', { timeZone: auth.user?.timezone || 'Asia/Shanghai' }) }
async function load(more = false) {
  if (disposed || props.readonly) return
  const request = ++listVersion, next = more ? page.value + 1 : 1
  loading.value = true; error.value = ''
  try {
    const result = await listProblems(bucket.value, appliedQuery.value, next)
    if (disposed || request !== listVersion) return
    options.value = more ? [...new Map([...options.value, ...result.items].map(item => [item.id, item])).values()] : result.items
    page.value = next; total.value = result.total
  } catch (cause) { if (!disposed && request === listVersion) error.value = errorMessage(cause) }
  finally { if (request === listVersion) loading.value = false }
}
async function refreshSelected() {
  const request = ++detailVersion, problemId = props.modelValue
  selected.value = null; detailError.value = ''; detailLoading.value = !!problemId
  if (!problemId) return
  try { const item = await getProblem(problemId); if (!disposed && request === detailVersion) selected.value = item }
  catch (cause) { if (!disposed && request === detailVersion) detailError.value = errorMessage(cause) }
  finally { if (request === detailVersion) detailLoading.value = false }
}
function search() { appliedQuery.value = query.value.trim(); void load() }
watch(() => props.modelValue, () => { void refreshSelected() }, { immediate: true })
watch(() => props.readonly, readonly => { if (!readonly) void load() }, { immediate: true })
onUnmounted(() => { disposed = true; ++listVersion; ++detailVersion })
</script>
<template>
  <section class="note-problem-link" aria-label="笔记关联问题">
    <h3>关联问题<span v-if="!readonly" class="muted"> · 保存笔记后生效</span></h3>
    <template v-if="!readonly">
      <div class="problem-select-grid"><div><label :for="`${id}-type`">问题类型</label><select :id="`${id}-type`" v-model="bucket" :disabled="disabled" @change="load()"><option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option></select></div><div><label :for="`${id}-problem`">问题选择</label><select :id="`${id}-problem`" :value="modelValue || ''" :disabled="disabled || loading" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value || null)"><option value="">不关联问题</option><option v-if="selectedOutside" :value="modelValue!">当前关联：{{ selected?.content.slice(0, 100) || '正在读取或不在筛选结果中' }}</option><option v-for="item in options" :key="item.id" :value="item.id">{{ item.is_resolved ? '✓ ' : '' }}{{ item.content.replace(/\s+/g, ' ').slice(0, 100) }}</option></select></div></div>
      <div class="problem-search"><label :for="`${id}-query`">搜索问题</label><input :id="`${id}-query`" v-model="query" maxlength="100" placeholder="按问题内容搜索" :disabled="disabled" @keydown.enter.prevent="search"><button type="button" class="quiet" :disabled="disabled || loading" @click="search">查询</button><button v-if="options.length < total" type="button" class="quiet" :disabled="disabled || loading" @click="load(true)">加载更多（{{ options.length }}/{{ total }}）</button></div>
      <p v-if="loading" class="muted" role="status">正在加载问题…</p><p v-else-if="!options.length && !error" class="muted">此类型没有匹配的问题。可更换类型，或到问题备忘中记录。</p>
      <p class="muted">类型用于筛选；切换类型不会清除已选问题。每篇笔记可关联一个问题。</p><p v-if="error" class="form-error" role="alert">{{ error }} <button type="button" class="quiet" @click="load()">重试</button></p>
    </template>
    <p v-if="detailLoading" class="muted">正在读取关联问题…</p>
    <div v-else-if="selected" class="linked-problem"><strong>{{ category }}</strong><p class="linked-content">{{ selected.content }}</p><p class="muted">记录 {{ time(selected.created_at) }}<span v-if="selected.resolved_at"> · 解决 {{ time(selected.resolved_at) }}</span></p><button type="button" class="quiet" :disabled="disabled || detailLoading" @click="refreshSelected">刷新问题状态</button></div>
    <p v-else-if="detailError" class="form-error" role="alert">{{ detailError }} <button type="button" class="quiet" @click="refreshSelected">重试</button><span v-if="!readonly">可选择“不关联问题”后保存，解除关联。</span></p>
    <p v-else-if="readonly" class="muted">此笔记未关联问题。</p>
  </section>
</template>
<style scoped>
.note-problem-link{margin:18px 0 24px;padding:18px 0;border-top:1px solid rgba(127,127,127,.2);border-bottom:1px solid rgba(127,127,127,.2);min-width:0}.note-problem-link h3{font-size:calc(15px * var(--ui-font-scale,1));font-weight:550;margin:0 0 16px}.note-problem-link p,.note-problem-link label{font-size:calc(12px * var(--ui-font-scale,1));line-height:1.8}.note-problem-link h3 span{font-size:calc(12px * var(--ui-font-scale,1))}.problem-select-grid{display:grid;grid-template-columns:minmax(120px,1fr) minmax(0,2fr);gap:14px}.problem-select-grid>div{min-width:0}.problem-select-grid label{display:block;margin:0 0 8px}select{width:100%;min-width:0;padding:10px;border:1px solid rgba(127,127,127,.35);border-radius:7px;color:inherit;font:inherit;font-size:calc(13px * var(--ui-font-scale,1))}.problem-search{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px}.problem-search label{margin:0}.problem-search input{flex:1;min-width:100px;max-width:280px;padding:9px}.quiet{background:transparent;color:inherit;border:1px solid transparent;padding:7px 10px;border-radius:6px;font:inherit;font-size:calc(12px * var(--ui-font-scale,1));cursor:pointer}.linked-problem{margin-top:14px;padding-left:12px;border-left:2px solid currentColor}.linked-problem strong{font-size:calc(12px * var(--ui-font-scale,1))}.linked-content{white-space:pre-wrap;overflow-wrap:anywhere;max-height:200px;overflow:auto}.note-problem-link .linked-content{font-size:calc(14px * var(--ui-font-scale,1))}@media(max-width:600px){.problem-select-grid{grid-template-columns:1fr}}
</style>
