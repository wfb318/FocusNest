<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { changeDocumentStorage, deleteDocument, downloadDocument, getDocument, listDocuments, renameDocument, uploadDocument } from '../api/documents'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import DocumentContent from '../components/DocumentContent.vue'
import { renderMarkdown } from '../utils/markdown'
import type { DocumentKind, DocumentStorageMode, DocumentSummary, WorkspaceDocument } from '../types/document'

const auth = useAuthStore()
const route = useRoute()
const selected = ref<WorkspaceDocument | null>(null)
const records = ref<DocumentSummary[]>([])
const picker = ref<HTMLInputElement | null>(null)
const reader = ref<HTMLElement | null>(null)
const renameDialog = ref<HTMLDialogElement | null>(null)
const deleteDialog = ref<HTMLDialogElement | null>(null)
const storageDialog = ref<HTMLDialogElement | null>(null)
const uploadMode = ref<DocumentStorageMode>('cloud')
const storageTarget = computed<DocumentStorageMode>(() => selected.value?.storage_mode === 'cloud_encrypted' ? 'cloud' : 'cloud_encrypted')
const storageLabel = (mode: DocumentStorageMode) => mode === 'cloud_encrypted' ? '云端加密' : '普通云端'
const renameTitle = ref('')
const rawMode = ref(false)
const busy = ref(false)
const reading = ref(false)
const loading = ref(false)
const error = ref('')
const listError = ref('')
const notice = ref('')
const page = ref(1)
const total = ref(0)
const pages = computed(() => Math.max(1, Math.ceil(total.value / 10)))
const filters = reactive({ q: '', kind: '' as '' | DocumentKind })
const preview = computed(() => selected.value?.kind === 'markdown' ? renderMarkdown(selected.value.content) : '')
let listRequest = 0
let detailRequest = 0
let disposed = false
const ownerId = auth.user?.id
const current = () => !disposed && auth.user?.id === ownerId

const kindLabel = (kind: DocumentKind) => ({markdown:'Markdown',text:'TXT',pdf:'PDF',word:'Word',presentation:'PPT',spreadsheet:'Excel'}[kind])
function localTime(value: string) { return new Date(value).toLocaleString('zh-CN', { timeZone: auth.user?.timezone || 'UTC' }) }
function size(value: number) { return value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KB` }
async function apply(value: WorkspaceDocument) {
  selected.value = value; rawMode.value = false
  await nextTick(); reader.value?.scrollTo({ top: 0 })
}
async function loadList() {
  const request = ++listRequest
  loading.value = true; listError.value = ''
  try {
    const result = await listDocuments({ page: page.value, page_size: 10, q: filters.q || undefined, kind: filters.kind || undefined })
    if (!current() || request !== listRequest) return
    records.value = result.items; total.value = result.total
    if (page.value > pages.value) { page.value = pages.value; await loadList() }
  } catch (cause) { if (current() && request === listRequest) listError.value = errorMessage(cause) }
  finally { if (request === listRequest) loading.value = false }
}
async function open(id: string) {
  if (busy.value) return
  const request = ++detailRequest
  reading.value = true; error.value = ''; notice.value = ''
  try {
    const result = await getDocument(id)
    if (current() && request === detailRequest) await apply(result)
  } catch (cause) { if (current() && request === detailRequest) error.value = errorMessage(cause) }
  finally { if (request === detailRequest) reading.value = false }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]; input.value = ''
  if (!file || busy.value || reading.value) return
  error.value = ''; notice.value = ''
  if (!/\.(md|markdown|txt|pdf|docx|pptx|xlsx|xls)$/i.test(file.name)) { error.value = '支持 MD、TXT、PDF、DOCX、PPTX、XLSX、XLS；旧 DOC/PPT 请先另存为新格式。'; return }
  const isText = /\.(md|markdown|txt)$/i.test(file.name)
  if (file.size > (isText ? 512 * 1024 : 10 * 1024 * 1024)) { error.value = isText ? '文本文件不能超过 512 KB。' : 'Office / PDF 文件不能超过 10 MB。'; return }
  busy.value = true
  try {
    const result = await uploadDocument(file, uploadMode.value)
    if (!current()) return
    await apply(result); filters.q = ''; filters.kind = ''; page.value = 1
    notice.value = `文档已保存 · ${storageLabel(result.storage_mode)}`; await loadList()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function download() {
  if (!selected.value || busy.value || reading.value) return
  const document = selected.value
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const blob = await downloadDocument(document.id)
    if (!current()) return
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url; link.download = document.filename
    window.document.body.append(link); link.click(); link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 30000)
    notice.value = '已发起原文件下载，请查看浏览器下载列表。'
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
function showRename() {
  if (!selected.value) return
  renameTitle.value = selected.value.title; error.value = ''; renameDialog.value?.showModal()
}
async function rename() {
  if (!selected.value || busy.value) return
  if (!renameTitle.value.trim()) { error.value = '请填写文档标题。'; return }
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const result = await renameDocument(selected.value.id, renameTitle.value, selected.value.revision)
    if (!current()) return
    await apply(result); renameDialog.value?.close(); notice.value = '标题已更新，原文件名和内容保持不变。'; await loadList()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function changeStorage() {
  const document = selected.value
  if (!document || busy.value || reading.value || !current()) return
  busy.value = true
  error.value = ''; notice.value = ''
  try {
    const result = await changeDocumentStorage(document.id, storageTarget.value, document.revision)
    if (!current()) return
    await apply(result)
    storageDialog.value?.close()
    notice.value = `已切换为${storageLabel(result.storage_mode)}。`
    await loadList()
  } catch (cause) {
    if (current()) error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (!selected.value || busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await deleteDocument(selected.value.id, selected.value.revision)
    if (!current()) return
    selected.value = null; deleteDialog.value?.close(); notice.value = '文档已删除。'; await loadList()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
function search() { page.value = 1; void loadList() }
function changePage(value: number) { page.value = value; void loadList() }
onBeforeRouteLeave(() => !auth.user || !busy.value)
onMounted(() => { void loadList(); if (typeof route.query.document === 'string') void open(route.query.document) })
watch(() => auth.user?.id, () => {
  selected.value = null
  records.value = []
  renameTitle.value = ''
  renameDialog.value?.close()
  storageDialog.value?.close()
  deleteDialog.value?.close()
}, { flush: 'sync' })
onUnmounted(() => { disposed = true; ++listRequest; ++detailRequest })
</script>

<template>
  <header class="page-header"><div><span class="eyebrow">YOUR READING SHELF</span><h1>文档资料库</h1><p class="muted">保存外部资料，随时阅读与取回原文件。</p></div>
    <div class="upload-actions">
      <label for="document-storage">上传保存方式</label>
      <select id="document-storage" v-model="uploadMode" :disabled="busy || reading">
        <option value="cloud">普通云端</option><option value="cloud_encrypted">云端加密</option>
      </select>
      <button class="quiet" :disabled="busy || reading" @click="picker?.click()">{{ busy ? '处理中…' : uploadMode === 'cloud_encrypted' ? '上传并加密' : '上传文档' }}</button>
    </div>
  </header>
  <input ref="picker" class="file-picker" type="file" accept=".md,.markdown,.txt,.pdf,.docx,.pptx,.xlsx,.xls" aria-label="选择上传文档" :disabled="busy || reading" @change="upload">
  <p class="upload-help muted">支持 PDF、Word（DOCX）、PPT（PPTX）、Excel（XLSX/XLS），最大 10 MB；MD/TXT 仍限 UTF-8、512 KB。上传即保存，Office 为内容预览。</p>
  <p v-if="uploadMode === 'cloud_encrypted'" class="muted">选择文件后，原件会发送至服务器，原件、文件名、标题和预览均加密保存。</p>
  <p v-if="error" class="feedback form-error" role="alert">{{ error }} <button v-if="selected" class="quiet" :disabled="busy || reading" @click="open(selected.id)">重新载入文档</button></p><p v-if="notice" class="feedback form-success" role="status">{{ notice }}</p>
  <div class="documents-layout">
    <aside class="panel library" aria-label="文档列表"><h2>我的资料</h2>
      <form class="filters" @submit.prevent="search"><label for="document-query">标题或文件名</label><input id="document-query" v-model="filters.q" maxlength="100" placeholder="搜索资料"><label for="document-kind">文件类型</label><select id="document-kind" v-model="filters.kind"><option value="">全部类型</option><option value="markdown">Markdown</option><option value="text">TXT</option><option value="pdf">PDF</option><option value="word">Word</option><option value="presentation">PPT</option><option value="spreadsheet">Excel</option></select><button class="quiet" :disabled="loading">查询</button></form>
      <p class="muted">关键词搜索普通云端文档。加密文档可按类型浏览。</p>
      <p v-if="listError" class="form-error" role="alert">{{ listError }}</p><p v-if="loading" class="muted">正在加载…</p><p v-else-if="!records.length && !listError" class="muted">没有符合条件的资料。可以上传一份文档开始阅读。</p>
      <ul v-if="!loading && !listError" class="document-list"><li v-for="item in records" :key="item.id"><button class="document-link" :class="{ current: selected?.id === item.id }" :aria-current="selected?.id === item.id ? 'true' : undefined" :disabled="busy" @click="open(item.id)"><strong>{{ item.title }}</strong><span>{{ item.filename || storageLabel(item.storage_mode) }}</span><small>{{ kindLabel(item.kind) }} · {{ size(item.size_bytes) }}</small></button></li></ul>
      <nav class="pagination" aria-label="文档分页"><span>共 {{ total }} 份 · {{ page }} / {{ pages }}</span><div><button class="quiet" :disabled="loading || page <= 1" @click="changePage(page - 1)">上一页</button><button class="quiet" :disabled="loading || page >= pages" @click="changePage(page + 1)">下一页</button></div></nav>
    </aside>
    <section ref="reader" :key="selected?.id ?? 'empty'" class="panel document-reader" tabindex="0" aria-label="文档阅读器" :aria-busy="reading">
      <p v-if="reading" role="status" class="muted">正在读取文档…</p>
      <template v-else-if="selected"><div class="reader-heading"><div><span class="eyebrow">{{ kindLabel(selected.kind) }} · {{ storageLabel(selected.storage_mode) }}</span><h2>{{ selected.title }}</h2><p class="muted metadata">{{ selected.filename }} · {{ size(selected.size_bytes) }}<br>上传于 {{ localTime(selected.created_at) }}</p></div><div class="reader-actions"><button v-if="selected.kind === 'markdown'" class="quiet" :disabled="busy" @click="rawMode = !rawMode">{{ rawMode ? '阅读预览' : '查看原文' }}</button><button class="quiet" :disabled="busy" @click="download">下载原文件</button><button class="quiet" :disabled="busy" @click="showRename">重命名</button><button class="quiet" :disabled="busy" @click="error = ''; storageDialog?.showModal()">切换保存方式</button><button class="quiet danger" :disabled="busy" @click="error = ''; deleteDialog?.showModal()">删除文档</button></div></div><DocumentContent v-if="!['markdown', 'text'].includes(selected.kind)" :key="selected.id" :document="selected"/><pre v-else-if="selected.kind === 'text' || rawMode" class="raw-content">{{ selected.content }}</pre><article v-else class="markdown-preview" aria-label="文档预览" v-html="preview"></article></template>
      <div v-else class="empty-reader"><span class="eyebrow">A SPACE FOR READING</span><h2>选一份资料，开始阅读</h2><p class="muted">点击左侧文档，或上传 PDF、Office、Markdown / TXT 文件。<br>资料只对当前账号可见。</p></div>
    </section>
  </div>
  <dialog ref="renameDialog" aria-labelledby="document-rename-title" @cancel.prevent="!busy && renameDialog?.close()"><h2 id="document-rename-title">重命名资料标题</h2><p class="muted">修改显示标题，原文件名和原文保持不变。</p><form @submit.prevent="rename"><fieldset :disabled="busy"><label for="document-title">标题</label><input id="document-title" v-model="renameTitle" maxlength="200" required><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="dialog-actions"><button class="quiet" type="button" @click="renameDialog?.close()">取消</button><button class="quiet" type="submit">保存标题</button></div></fieldset></form></dialog>
  <dialog ref="deleteDialog" aria-labelledby="document-delete-title" @cancel.prevent="!busy && deleteDialog?.close()"><h2 id="document-delete-title">删除“{{ selected?.title }}”？</h2><p>删除后无法从资料库恢复。需要保留原件时，请先下载。</p><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="dialog-actions"><button class="quiet" :disabled="busy" autofocus @click="deleteDialog?.close()">保留文档</button><button class="quiet danger" :disabled="busy" @click="remove">确认删除</button></div></dialog>
  <dialog ref="storageDialog" aria-labelledby="document-storage-title" @cancel.prevent="!busy && storageDialog?.close()">
    <h2 id="document-storage-title">切换为{{ storageLabel(storageTarget) }}？</h2>
    <p v-if="storageTarget === 'cloud_encrypted'">原件、标题、文件名和预览将在当前记录中加密保存。旧数据库备份可能保留明文。</p>
    <p v-else>原件、标题、文件名和预览将以明文写入服务器数据库。</p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <div class="dialog-actions">
      <button class="quiet" :disabled="busy" autofocus @click="storageDialog?.close()">取消</button>
      <button class="quiet" :disabled="busy" @click="changeStorage">{{ busy ? '正在校验并切换…' : '确认切换' }}</button>
    </div>
  </dialog>
</template>

<style scoped>
.upload-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.upload-actions select{padding:8px;border:1px solid #b6c9bb;border-radius:8px}
h1{margin:12px 0}.file-picker{position:absolute;width:1px;height:1px;opacity:0;overflow:hidden}.upload-help,.feedback{padding:12px 16px;border-radius:10px;background:#ffffffb3;font-size:calc(13px * var(--ui-font-scale,1))}.quiet{padding:9px 13px;border-radius:8px;color:var(--text-primary,#263c34);font-size:calc(13px * var(--ui-font-scale,1))}.danger{color:#ad4141}.documents-layout{display:grid;grid-template-columns:290px minmax(0,1fr);gap:20px;margin-top:20px;align-items:start}.library{position:sticky;top:20px;max-height:calc(100dvh - 40px);overflow:auto;padding:20px;scrollbar-gutter:stable}.library h2{margin:0 0 12px}.filters label{margin:14px 0 7px}.filters input{padding:10px}.filters select{display:block;width:100%;padding:10px;margin-bottom:12px;border:1px solid #b6c9bb;border-radius:8px;color:var(--text-primary,#263c34)}.document-list{list-style:none;padding:0;margin:18px 0;display:grid;gap:8px}.document-link{display:flex;flex-direction:column;gap:6px;width:100%;padding:13px;border:1px solid #ffffffb3;border-radius:10px;background:#ffffff59;color:var(--text-primary,#263c34);text-align:left;overflow-wrap:anywhere}.document-link.current{background:#dceee3b8;border-color:#76a48a}.document-link strong{font-size:calc(14px * var(--ui-font-scale,1));line-height:1.6}.document-link span,.document-link small{font-size:calc(12px * var(--ui-font-scale,1));color:var(--text-muted,#586d60);line-height:1.6}.pagination{font-size:calc(12px * var(--ui-font-scale,1))}.pagination>div{display:flex;gap:8px;margin-top:10px}.document-reader{min-width:0;height:clamp(420px,calc(100dvh - 280px),900px);overflow:auto;overscroll-behavior:contain;overflow-anchor:none;scrollbar-gutter:stable}.reader-heading{border-bottom:1px solid #d7dfd5;padding-bottom:18px;margin-bottom:24px;overflow-wrap:anywhere}.reader-heading h2{font-size:calc(24px * var(--ui-font-scale,1));margin:10px 0}.metadata{font-size:calc(12px * var(--ui-font-scale,1))}.reader-actions{display:flex;gap:10px;flex-wrap:wrap}.raw-content{white-space:pre-wrap;overflow-wrap:anywhere;font:calc(14px * var(--ui-font-scale,1))/1.9 ui-monospace,monospace;margin:0}.markdown-preview{font-size:calc(14px * var(--ui-font-scale,1));line-height:1.9;overflow-wrap:anywhere}.markdown-preview :deep(pre){overflow:auto;background:#ffffff70;padding:16px;border-radius:8px}.markdown-preview :deep(code){font-family:ui-monospace,monospace}.markdown-preview :deep(blockquote){border-left:3px solid #a3b69c;padding-left:16px;color:var(--text-muted,#586d60)}.markdown-preview :deep(table){border-collapse:collapse;display:block;overflow:auto}.markdown-preview :deep(th),.markdown-preview :deep(td){padding:8px;border:1px solid #b6c9bb}.markdown-preview :deep(a){text-decoration:underline;color:var(--text-primary,#263c34)}.empty-reader{padding:60px 12px;text-align:center}.dialog-actions{display:flex;gap:12px;margin-top:20px}dialog{max-width:440px;width:calc(100% - 40px);padding:26px;border-radius:14px;color:var(--text-primary,#263c34)}dialog p{font-size:calc(14px * var(--ui-font-scale,1));line-height:1.8}dialog::backdrop{background:#203c3459}fieldset{border:0;padding:0;margin:0;min-width:0}@media(max-width:1100px){.documents-layout{grid-template-columns:1fr}.library{position:static;max-height:45dvh}.document-reader{height:auto;min-height:360px;max-height:80dvh}}
</style>
