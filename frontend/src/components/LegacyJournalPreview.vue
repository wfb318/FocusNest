<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { cloudJournalTransport } from '../api/journals'
import { errorMessage } from '../api/client'
import { createJournalStorage, JournalStorageError } from '../services/journalStorage'
import { useAuthStore } from '../stores/auth'
import { renderJournalMarkdown } from '../utils/markdown'
import type { Journal, JournalSummary } from '../types/journal'

const emit = defineEmits<{ close: [] }>()
const auth = useAuthStore()
const ownerId = auth.user?.id
let active = true, version = 0
const storage = createJournalStorage('cloud', cloudJournalTransport, { purpose: 'legacy-migration', isCurrent: () => active && !!ownerId && auth.user?.id === ownerId })
const records = ref<JournalSummary[]>([]), entry = ref<Journal | null>(null)
const total = ref<number | null>(null), page = ref(1), busy = ref(false), error = ref('')
const pages = computed(() => Math.max(1, Math.ceil((total.value ?? 0) / 10)))
const preview = computed(() => renderJournalMarkdown(entry.value?.content || ''))
const status = computed(() => total.value === null ? '历史云端日记：尚未确认' : total.value > 0 ? `历史云端日记待迁移 · ${total.value} 篇` : '当前账号没有历史云端日记')

function clear() {
  active = false; ++version
  records.value = []; entry.value = null; total.value = null; error.value = ''; busy.value = false
}
watch(() => auth.user?.id, () => { clear(); emit('close') }, { flush: 'sync' })
async function loadPage(target = page.value) {
  if (busy.value || !active) return
  const request = ++version
  busy.value = true; error.value = ''; entry.value = null
  try {
    const result = await storage.list({ page: target, page_size: 10 })
    if (!active || request !== version) return
    records.value = result.items; total.value = result.total; page.value = target
  } catch (cause) {
    if (active && request === version) error.value = cause instanceof JournalStorageError ? cause.message : errorMessage(cause)
  } finally { if (active && request === version) busy.value = false }
}
async function openDay(date: string) {
  if (busy.value || !active) return
  const request = ++version
  busy.value = true; error.value = ''; entry.value = null
  try {
    const result = await storage.getDay(date)
    if (active && request === version) {
      entry.value = result.entry
      if (!result.entry) error.value = '这篇历史日记已不存在，请刷新列表。'
    }
  } catch (cause) {
    if (active && request === version) error.value = cause instanceof JournalStorageError ? cause.message : errorMessage(cause)
  } finally { if (active && request === version) busy.value = false }
}
function close() { clear(); emit('close') }
onMounted(() => { void loadPage() })
onUnmounted(clear)
</script>

<template>
  <section class="panel legacy-panel" aria-labelledby="legacy-journal-title">
    <div class="heading"><h2 id="legacy-journal-title">历史云端日记 · 只读</h2><button class="quiet" @click="close">关闭历史查看</button></div>
    <p class="muted">你已主动打开服务器中的旧日记。这里提供只读查看；复制到本地请使用本页“导入 Markdown 日记 / 迁移历史云端日记”。复制不会自动清理云端，此处内容仍来自原服务器，尚未加密。</p>
    <p role="status">{{ status }}</p>
    <p v-if="busy" class="muted" role="status">正在读取历史记录…</p>
    <p v-if="error" class="form-error" role="alert">{{ error }} <button class="quiet" :disabled="busy" @click="loadPage()">重试列表</button></p>
    <ul class="entries"><li v-for="item in records" :key="item.id"><button class="quiet entry" :disabled="busy" @click="openDay(item.entry_date)"><time>{{ item.entry_date }}</time><strong>{{ item.title || '这一天的记录' }}</strong><span>只读查看 →</span></button></li></ul>
    <nav v-if="total !== null" class="pagination" aria-label="历史云端日记分页"><span>第 {{ page }} / {{ pages }} 页</span><button class="quiet" :disabled="busy || page <= 1" @click="loadPage(page - 1)">上一页</button><button class="quiet" :disabled="busy || page >= pages" @click="loadPage(page + 1)">下一页</button></nav>
    <article v-if="entry" class="legacy-article"><p class="muted">{{ entry.entry_date }} · 云端原件</p><h3>{{ entry.title || '这一天的记录' }}</h3><div class="markdown-preview" v-html="preview"></div></article>
  </section>
</template>

<style scoped>
.legacy-panel{margin-top:24px;padding:24px!important}.heading,.pagination{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.legacy-panel p{line-height:1.8}.quiet{padding:10px 14px;border-radius:8px;font:inherit;cursor:pointer}.entries{list-style:none;padding:0;display:grid;gap:12px}.entry{display:flex;align-items:center;gap:20px;text-align:left;width:100%}.entry strong{flex:1;overflow-wrap:anywhere}.entry time,.entry span,.pagination{font-size:calc(12px * var(--ui-font-scale,1))}.legacy-article{border-top:1px solid rgba(127,127,127,.25);margin-top:24px;padding-top:16px}.markdown-preview{max-height:600px;overflow:auto;overflow-wrap:anywhere;line-height:1.9}.markdown-preview :deep(pre){overflow:auto}.markdown-preview :deep(table){display:block;overflow:auto}.markdown-preview :deep(a){text-decoration:underline}@media(max-width:600px){.entry{align-items:flex-start;flex-direction:column;gap:8px}}
</style>
