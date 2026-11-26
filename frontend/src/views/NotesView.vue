<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { changeNoteStorage, createNote, deleteNote, getNote, listNotes, updateNote } from '../api/notes'
import { createFolder, deleteFolder, listFolders, renameFolder } from '../api/noteFolders'
import type { NoteFolder } from '../api/noteFolders'
import { folderRows } from '../utils/folderTree'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { renderMarkdown } from '../utils/markdown'
import { IMPORT_ACCEPT, readNoteFile } from '../utils/noteImport'
import type { Note, NoteStorageMode, NoteSummary } from '../types/note'
import NoteProblemLink from '../components/NoteProblemLink.vue'

const auth = useAuthStore()
const route = useRoute()
const saved = ref<Note | null>(null)
const importPicker = ref<HTMLInputElement | null>(null)
const editorPanel = ref<HTMLElement | null>(null)
const form = reactive({
  title: '', content: '', pinned: false,
  folder_id: null as string | null,
  problem_id: null as string | null,
  storage_mode: 'cloud' as NoteStorageMode,
})
const dirty = computed(() =>
  form.title !== (saved.value?.title ?? '') ||
  form.content !== (saved.value?.content ?? '') ||
  form.pinned !== (saved.value?.pinned ?? false) ||
  form.folder_id !== (saved.value?.folder_id ?? null) ||
  form.problem_id !== (saved.value?.problem_id ?? null) ||
  form.storage_mode !== (saved.value?.storage_mode ?? 'cloud')
)
const preview = computed(() => renderMarkdown(form.content))
const readMode = ref(false)
const busy = ref(false)
const loading = ref(false)
const error = ref('')
const listError = ref('')
const notice = ref('')
const records = ref<NoteSummary[]>([])
const page = ref(1)
const total = ref(0)
const pages = computed(() => Math.max(1, Math.ceil(total.value / 10)))
const filters = reactive({ q: '', pinned: false })
const discardDialog = ref<HTMLDialogElement | null>(null)
const deleteDialog = ref<HTMLDialogElement | null>(null)
const storageDialog = ref<HTMLDialogElement | null>(null)
const storageError = ref('')
const storageTarget = computed<NoteStorageMode>(() =>
  saved.value?.storage_mode === 'cloud_encrypted' ? 'cloud' : 'cloud_encrypted'
)
function storageLabel(mode: NoteStorageMode) {
  return mode === 'cloud_encrypted' ? '云端加密' : '普通云端'
}
let confirmDiscard: ((value: boolean) => void) | undefined
let requestId = 0
let disposed = false

const folders = ref<NoteFolder[]>([])
const scope = ref('')
const collapsed = ref(new Set<string>())
const folderError = ref('')
const folderLoading = ref(false)
const folderDialog = ref<HTMLDialogElement | null>(null)
const folderDeleteDialog = ref<HTMLDialogElement | null>(null)
const editingFolder = ref<NoteFolder | null>(null)
const folderForm = reactive({ name: '', parent_id: null as string | null })
const tree = computed(() => folderRows(folders.value, collapsed.value))
const currentFolder = computed(() => folders.value.find(folder => folder.id === scope.value))
const scopeLabel = computed(() => scope.value === 'unfiled' ? '未分类' : tree.value.find(row => row.folder.id === scope.value)?.path ?? '全部笔记')
function toggleFolder(id: string) {
  const next = new Set(collapsed.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  collapsed.value = next
}
async function refreshFolders() {
  if (folderLoading.value) return
  folderLoading.value = true; folderError.value = ''
  try {
    const result = await listFolders()
    if (disposed) return
    folders.value = result
    if (scope.value && scope.value !== 'unfiled' && !result.some(f => f.id === scope.value)) { scope.value = ''; page.value = 1; await loadList() }
  } catch (cause) { folderError.value = errorMessage(cause) }
  finally { folderLoading.value = false }
}
function chooseFolder(id: string) { scope.value = id; page.value = 1; void loadList() }
function folderName(id: string | null) { return tree.value.find(row => row.folder.id === id)?.path ?? (id ? '文件夹待同步' : '未分类') }
function showFolderDialog(rename = false) {
  editingFolder.value = rename ? currentFolder.value ?? null : null
  folderForm.name = editingFolder.value?.name ?? ''
  folderForm.parent_id = editingFolder.value?.parent_id ?? currentFolder.value?.id ?? null
  folderError.value = ''; folderDialog.value?.showModal()
}
async function submitFolder() {
  if (busy.value) return
  busy.value = true; folderError.value = ''
  try {
    const folder = editingFolder.value ? await renameFolder(editingFolder.value, folderForm.name) : await createFolder(folderForm.name, folderForm.parent_id)
    await refreshFolders()
    scope.value = folder.id; page.value = 1
    if (folder.parent_id) { const next = new Set(collapsed.value); next.delete(folder.parent_id); collapsed.value = next }
    folderDialog.value?.close(); await loadList()
  } catch (cause) { folderError.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function removeFolder() {
  const folder = currentFolder.value
  if (busy.value || !folder) return
  busy.value = true; folderError.value = ''
  try {
    await deleteFolder(folder)
    scope.value = 'unfiled'; page.value = 1
    // Preserve drafts. A stale editor must explicitly reload the new server version.
    if (saved.value?.folder_id === folder.id) error.value = '文件夹已删除，笔记已移到未分类。当前输入保留，请复制需要的内容后重新载入笔记。'
    folderDeleteDialog.value?.close(); await refreshFolders(); await loadList()
  } catch (cause) { folderError.value = errorMessage(cause) }
  finally { busy.value = false }
}

function apply(note: Note | null) {
  saved.value = note
  form.title = note?.title ?? ''; form.content = note?.content ?? ''; form.pinned = note?.pinned ?? false; form.folder_id = note?.folder_id ?? null; form.problem_id = note?.problem_id ?? null
  form.storage_mode = note?.storage_mode ?? 'cloud'
}
function mayDiscard(): Promise<boolean> {
  if (!dirty.value) return Promise.resolve(true)
  if (confirmDiscard) return Promise.resolve(false)
  return new Promise(resolve => { confirmDiscard = resolve; discardDialog.value?.showModal() })
}
function resolveDiscard(value: boolean) {
  discardDialog.value?.close(); confirmDiscard?.(value); confirmDiscard = undefined
}
async function openNote(id?: string) {
  if (busy.value || !(await mayDiscard()) || busy.value || disposed) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const note = id ? await getNote(id) : null
    if (!disposed) { apply(note); if (!id) form.folder_id = currentFolder.value?.id ?? null; readMode.value = !!note; await nextTick(); editorPanel.value?.scrollTo({ top: 0 }) }
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || busy.value) return
  const targetFolder = currentFolder.value?.id ?? null
  busy.value = true; error.value = ''; notice.value = ''
  try {
    // Validate before asking to discard, so a bad file never clears a good draft.
    const imported = await readNoteFile(file)
    if (disposed || !(await mayDiscard()) || disposed) return
    apply(null)
    form.title = imported.title; form.content = imported.content; form.folder_id = targetFolder
    readMode.value = false
    await nextTick(); editorPanel.value?.scrollTo({ top: 0 })
    notice.value = '文件已读入新笔记草稿，尚未保存。请确认内容和所属文件夹后点击“保存笔记”。'
  } catch (cause) {
    if (!disposed) error.value = cause instanceof Error ? cause.message : '文件导入失败，原有输入已保留。'
  } finally { busy.value = false }
}
async function loadList() {
  const request = ++requestId
  loading.value = true; listError.value = ''
  try {
    const result = await listNotes({ page: page.value, page_size: 10, q: filters.q || undefined, pinned: filters.pinned ? true : undefined, folder_id: scope.value && scope.value !== 'unfiled' ? scope.value : undefined, unfiled: scope.value === 'unfiled' || undefined })
    if (disposed || request !== requestId) return
    records.value = result.items; total.value = result.total
    if (page.value > pages.value) { page.value = pages.value; await loadList() }
  } catch (cause) { if (!disposed && request === requestId) listError.value = errorMessage(cause) }
  finally { if (request === requestId) loading.value = false }
}
async function save() {
  if (busy.value) return
  if (!form.title.trim() || !form.content.trim()) { error.value = '请填写标题和正文。'; return }
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const note = saved.value ? await updateNote(saved.value.id, { ...form }, saved.value.revision) : await createNote({ ...form })
    if (disposed) return
    apply(note); notice.value = `笔记已保存 · ${storageLabel(note.storage_mode)}`; page.value = 1; await loadList()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
function showStorageDialog() {
  if (busy.value || dirty.value || !saved.value) return
  storageError.value = ''
  storageDialog.value?.showModal()
}
function closeStorageDialog() {
  if (!busy.value) storageDialog.value?.close()
}
async function changeStorage() {
  const note = saved.value
  const owner = auth.user?.id
  if (busy.value || dirty.value || !note || !owner) return
  busy.value = true
  storageError.value = ''
  notice.value = ''
  try {
    const updated = await changeNoteStorage(note.id, storageTarget.value, note.revision)
    if (disposed || auth.user?.id !== owner) return
    apply(updated)
    storageDialog.value?.close()
    notice.value = `已切换为${storageLabel(updated.storage_mode)}。`
    await loadList()
  } catch (cause) {
    if (!disposed && auth.user?.id === owner) storageError.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (busy.value || !saved.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await deleteNote(saved.value.id, saved.value.revision)
    if (disposed) return
    apply(null); readMode.value = false; deleteDialog.value?.close()
    notice.value = '笔记已删除。'; await loadList()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
function search() { page.value = 1; void loadList() }
function changePage(value: number) { page.value = value; void loadList() }
function closeDelete() { if (!busy.value) deleteDialog.value?.close() }
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
function localTime(value: string) { return new Date(value).toLocaleString('zh-CN', { timeZone: auth.user?.timezone || 'UTC' }) }
onBeforeRouteLeave(() => { if (!auth.user) return true; return busy.value ? false : mayDiscard() })
onMounted(() => { void refreshFolders(); void loadList(); if (typeof route.query.note === 'string') void openNote(route.query.note); window.addEventListener('beforeunload', beforeUnload) })
onUnmounted(() => { disposed = true; ++requestId; resolveDiscard(false); window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <header class="page-header"><div><span class="eyebrow">IDEAS WORTH KEEPING</span><h1>笔记</h1><p class="muted">收集知识、代码与想法，让它们慢慢生长。</p></div><div class="note-header-actions"><button class="quiet" :disabled="busy" @click="importPicker?.click()">导入文档</button><button class="quiet" :disabled="busy" @click="openNote()">新建笔记</button></div></header>
  <input ref="importPicker" class="import-picker" type="file" :accept="IMPORT_ACCEPT" aria-label="选择要导入的文档" :disabled="busy" @change="importFile">
  <p class="muted small">可导入 UTF-8 编码的 Markdown / TXT 文件，最大 512 KB。导入后先预览，点击保存才写入笔记。</p>
  <p v-if="error" class="form-error" role="alert">{{ error }} <button v-if="saved" class="quiet" :disabled="busy" @click="openNote(saved.id)">重新载入</button></p>
  <p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  <div class="notes-layout">
  <aside class="panel folder-sidebar" aria-label="笔记文件夹">
    <h2>文件夹</h2>
    <div class="folder-actions"><button class="quiet" :disabled="busy || folderLoading" @click="showFolderDialog()">新建文件夹</button><button class="quiet" :disabled="busy || folderLoading" @click="refreshFolders">刷新</button></div>
    <p v-if="folderError" class="form-error" role="alert">{{ folderError }}</p>
    <nav aria-label="文件夹分类">
      <button class="folder-link" :class="{ selected: scope === '' }" @click="chooseFolder('')">全部笔记</button>
      <button class="folder-link" :class="{ selected: scope === 'unfiled' }" @click="chooseFolder('unfiled')">未分类</button>
      <div v-for="row in tree.filter(item => item.visible)" :key="row.folder.id" class="folder-row" :style="{ paddingLeft: `${Math.min(row.depth, 8) * 14}px` }">
        <button v-if="row.hasChildren" class="folder-toggle" :aria-label="`${collapsed.has(row.folder.id) ? '展开' : '折叠'} ${row.folder.name}`" :aria-expanded="!collapsed.has(row.folder.id)" @click="toggleFolder(row.folder.id)">{{ collapsed.has(row.folder.id) ? '▸' : '▾' }}</button><span v-else class="folder-spacer"></span>
        <button class="folder-link" :title="row.path" :class="{ selected: scope === row.folder.id }" @click="chooseFolder(row.folder.id)">📁 {{ row.folder.name }}</button>
      </div>
    </nav>
    <div v-if="currentFolder" class="folder-actions"><button class="quiet" :disabled="busy" @click="showFolderDialog(true)">重命名</button><button class="quiet danger" :disabled="busy" @click="folderError = ''; folderDeleteDialog?.showModal()">删除文件夹</button></div>
    <p class="muted small">选择文件夹后点击“新建文件夹”，可创建子文件夹。列表只显示该文件夹直属的笔记。</p>
  <section class="history" aria-label="笔记列表"><h2>{{ scopeLabel }}</h2>
    <form class="filters" @submit.prevent="search"><div><label for="note-query">标题或正文关键词</label><input id="note-query" v-model="filters.q" maxlength="100" placeholder="搜索自己的笔记"></div><label class="check"><input v-model="filters.pinned" type="checkbox">只看置顶</label><button class="quiet" :disabled="loading">查询</button></form>
    <p class="muted small">关键词只搜索普通云端笔记。加密笔记可按文件夹、置顶和时间浏览。</p>
    <p v-if="listError" class="form-error" role="alert">{{ listError }}</p><p v-if="loading" class="muted">正在加载笔记…</p><p v-else-if="!records.length && !listError" class="muted">没有符合条件的笔记，可以从上方开始记录。</p>
    <ul v-if="!loading && !listError" class="entries"><li v-for="note in records" :key="note.id"><button class="entry" :class="{ current: saved?.id === note.id }" :aria-current="saved?.id === note.id ? 'true' : undefined" :disabled="busy" @click="openNote(note.id)"><strong>{{ note.pinned ? '置顶 · ' : '' }}{{ note.title }}</strong><span v-if="!scope">{{ folderName(note.folder_id) }}</span><time>{{ localTime(note.updated_at) }}</time><span>{{ saved?.id === note.id ? '正在打开' : '打开笔记 →' }}</span></button></li></ul>
    <nav class="buttons pagination" aria-label="笔记分页"><span>共 {{ total }} 篇 · {{ page }} / {{ pages }}</span><button class="quiet" :disabled="loading || page <= 1" @click="changePage(page - 1)">上一页</button><button class="quiet" :disabled="loading || page >= pages" @click="changePage(page + 1)">下一页</button></nav>
  </section>
  </aside>
  <div class="notes-content">
  <section ref="editorPanel" :key="saved?.id ?? 'draft'" class="panel editor-panel" aria-label="笔记编辑器" tabindex="0">
    <div class="toolbar"><span class="muted">{{ dirty ? '有未保存的修改' : saved ? '已保存' : '新笔记' }} · {{ storageLabel(form.storage_mode) }}</span><button class="quiet" :disabled="busy" @click="readMode = !readMode">{{ readMode ? '编辑笔记' : '阅读模式' }}</button></div>
    <NoteProblemLink v-model="form.problem_id" :readonly="readMode" :disabled="busy" />
    <div v-if="readMode"><h2 class="note-title">{{ form.title || '未命名笔记' }}</h2><p v-if="dirty" class="muted">正在预览未保存的内容。</p><article class="markdown-preview" aria-label="Markdown 预览" v-html="preview"></article><p v-if="!form.content" class="muted">点击“编辑笔记”开始书写。</p></div>
    <form v-else @submit.prevent="save"><fieldset :disabled="busy">
      <label for="note-title">标题</label><input id="note-title" v-model="form.title" maxlength="200" required placeholder="这篇笔记关于什么？">
      <template v-if="!saved">
        <label for="note-storage">保存方式</label>
        <select id="note-storage" v-model="form.storage_mode" aria-describedby="note-storage-hint">
          <option value="cloud">普通云端</option>
          <option value="cloud_encrypted">云端加密</option>
        </select>
        <p v-if="form.storage_mode === 'cloud_encrypted'" id="note-storage-hint" class="muted small">服务器加密标题和正文。文件夹、置顶和问题关联仍可用于组织笔记。</p>
        <p v-else id="note-storage-hint" class="muted small">标题和正文以明文存入服务器数据库，可按关键词搜索。</p>
      </template>
      <label for="note-folder">所属文件夹（保存后生效）</label><select id="note-folder" v-model="form.folder_id"><option :value="null">未分类</option><option v-if="form.folder_id && !folders.some(f => f.id === form.folder_id)" :value="form.folder_id" disabled>原文件夹不可用，请重新选择</option><option v-for="row in tree" :key="row.folder.id" :value="row.folder.id">{{ row.path }}</option></select>
      <label class="check"><input v-model="form.pinned" type="checkbox">置顶（保存后生效）</label>
      <div class="writing-grid"><div><label for="note-content">正文（Markdown）</label><textarea id="note-content" v-model="form.content" maxlength="100000" rows="18" required placeholder="写下知识、想法或代码…"></textarea></div><div><h2>预览</h2><article class="markdown-preview" aria-label="Markdown 预览" v-html="preview"></article></div></div>
      <p class="muted small">{{ form.content.length }} / 100000 字符 · 手动保存 · 预览不执行 HTML 或自动加载图片。</p>
      <div class="buttons"><button type="submit" class="primary-button" :disabled="!dirty">{{ busy ? '处理中…' : '保存笔记' }}</button><button type="button" class="quiet" :disabled="!dirty" @click="openNote(saved?.id)">放弃修改</button></div>
    </fieldset></form>
    <div v-if="saved" class="toolbar metadata">
      <span class="muted">{{ saved.pinned ? '已置顶 · ' : '' }}{{ folderName(saved.folder_id) }} · 更新于 {{ localTime(saved.updated_at) }}</span>
      <div class="note-header-actions">
        <button class="quiet" :disabled="busy || dirty" :title="dirty ? '请先保存或放弃修改' : undefined" @click="showStorageDialog">切换保存方式</button>
        <button class="quiet danger" :disabled="busy" @click="deleteDialog?.showModal()">删除笔记</button>
      </div>
    </div>
  </section>

  </div></div>
  <dialog ref="folderDialog" aria-labelledby="folder-dialog-title" @cancel.prevent="!busy && folderDialog?.close()"><h2 id="folder-dialog-title">{{ editingFolder ? '重命名文件夹' : '新建文件夹' }}</h2><form @submit.prevent="submitFolder"><fieldset :disabled="busy"><label for="folder-name">文件夹名称</label><input id="folder-name" v-model="folderForm.name" maxlength="100" required><template v-if="!editingFolder"><label for="folder-parent">上级文件夹</label><select id="folder-parent" v-model="folderForm.parent_id"><option :value="null">根目录</option><option v-for="row in tree" :key="row.folder.id" :value="row.folder.id">{{ row.path }}</option></select></template><p v-if="folderError" class="form-error" role="alert">{{ folderError }}</p><div class="buttons"><button class="quiet" type="button" @click="folderDialog?.close()">取消</button><button class="quiet" type="submit">保存文件夹</button></div></fieldset></form></dialog>
  <dialog ref="folderDeleteDialog" aria-labelledby="folder-delete-title" @cancel.prevent="!busy && folderDeleteDialog?.close()"><h2 id="folder-delete-title">删除文件夹“{{ currentFolder?.name }}”？</h2><p>其中的笔记将保留并移到“未分类”。如有子文件夹，请先处理子文件夹。</p><p v-if="folderError" class="form-error" role="alert">{{ folderError }}</p><div class="buttons"><button class="quiet" :disabled="busy" @click="folderDeleteDialog?.close()">取消</button><button class="quiet danger" :disabled="busy" @click="removeFolder">确认删除文件夹</button></div></dialog>
  <dialog ref="discardDialog" aria-labelledby="note-discard-title" @cancel.prevent="resolveDiscard(false)"><h2 id="note-discard-title">放弃未保存的修改？</h2><p>当前输入尚未保存，可以返回继续编辑或先保存。</p><div class="buttons"><button class="quiet" autofocus @click="resolveDiscard(false)">继续编辑</button><button class="quiet danger" @click="resolveDiscard(true)">放弃修改并继续</button></div></dialog>
  <dialog ref="deleteDialog" aria-labelledby="note-delete-title" @cancel.prevent="closeDelete"><h2 id="note-delete-title">删除这篇笔记？</h2><p>删除后无法恢复，本页未保存的修改也会被清空。</p><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="buttons"><button class="quiet" autofocus :disabled="busy" @click="closeDelete">保留笔记</button><button class="quiet danger" :disabled="busy" @click="remove">确认删除</button></div></dialog>
  <dialog ref="storageDialog" aria-labelledby="note-storage-title" @cancel.prevent="closeStorageDialog">
    <h2 id="note-storage-title">切换为{{ storageLabel(storageTarget) }}？</h2>
    <p v-if="storageTarget === 'cloud_encrypted'">标题和正文将加密存入同一条笔记。切换完成后，从列表打开笔记即可查看内容。旧数据库备份可能保留明文。</p>
    <p v-else>标题和正文将以明文写入服务器数据库，并可在普通笔记搜索中找到。</p>
    <p v-if="storageError" class="form-error" role="alert">{{ storageError }}</p>
    <div class="buttons">
      <button class="quiet" autofocus :disabled="busy" @click="closeStorageDialog">取消</button>
      <button class="quiet" :disabled="busy" @click="changeStorage">{{ busy ? '正在校验并切换…' : '确认切换' }}</button>
    </div>
  </dialog>
</template>

<style scoped>
.note-header-actions{display:flex;gap:12px;flex-wrap:wrap}.import-picker{position:absolute;width:1px;height:1px;opacity:0;overflow:hidden}
.notes-layout{display:grid;grid-template-columns:290px minmax(0,1fr);gap:20px;margin-top:22px}.notes-content{min-width:0}.folder-sidebar{align-self:start;padding:18px;position:sticky;top:20px}.folder-sidebar h2{font-size:calc(16px * var(--ui-font-scale,1));margin-top:0}.folder-actions{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.folder-actions .quiet{padding:7px;font-size:calc(12px * var(--ui-font-scale,1))}.folder-link{display:block;width:100%;text-align:left;border:0;background:transparent;padding:9px 6px;border-radius:7px;color:var(--text-primary,#263c34);overflow-wrap:anywhere}.folder-link.selected{background:#e6eee4;font-weight:600}.folder-row{display:flex;align-items:center}.folder-toggle{border:0;background:transparent;color:var(--text-primary,#263c34);padding:4px}.folder-spacer{width:18px;flex-shrink:0}.folder-sidebar nav{max-height:480px;overflow:auto}select{width:100%;padding:10px;border:1px solid #d7dfd5;border-radius:8px;color:var(--text-primary,#263c34);background:#fcfdfb;margin-bottom:12px}.notes-layout .editor-panel{margin-top:0}@media(max-width:1100px){.notes-layout{grid-template-columns:1fr}.folder-sidebar{position:static}.folder-sidebar nav{max-height:250px}}

h1{margin:12px 0}.editor-panel{margin-top:22px}.toolbar,.buttons{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.toolbar{margin-bottom:20px}.metadata{margin:24px 0 0;font-size:calc(12px * var(--ui-font-scale,1))}.buttons{justify-content:flex-start;margin-top:20px}.quiet{border:1px solid #d7dfd5;background:#fff;color:var(--text-primary,#263c34);border-radius:8px;padding:10px 14px}.danger{color:#ad4141}.primary-button{width:auto;margin:0}fieldset{border:0;margin:0;padding:0;min-width:0}.check{display:flex;align-items:center;gap:8px;margin:16px 0}.check input{width:auto;margin:0}.writing-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.writing-grid>div{min-width:0}.writing-grid h2,.writing-grid label{font-size:calc(14px * var(--ui-font-scale,1));margin:0 0 12px}textarea{width:100%;min-height:360px;resize:vertical;border:1px solid #d7dfd5;border-radius:10px;padding:16px;background:#fcfdfb;color:var(--text-primary,#263c34);font:calc(14px * var(--ui-font-scale,1))/1.8 ui-monospace,monospace}.markdown-preview{overflow-wrap:anywhere;font-size:calc(14px * var(--ui-font-scale,1));line-height:1.9}.writing-grid .markdown-preview{max-height:640px;overflow:auto}.markdown-preview :deep(pre){overflow:auto;background:#f0f3ed;padding:16px;border-radius:8px}.markdown-preview :deep(code){font-family:ui-monospace,monospace}.markdown-preview :deep(blockquote){border-left:3px solid #a3b69c;padding-left:16px;color:var(--text-muted,#586d60)}.markdown-preview :deep(table){border-collapse:collapse;display:block;overflow:auto}.markdown-preview :deep(th),.markdown-preview :deep(td){padding:8px;border:1px solid #d7dfd5}.markdown-preview :deep(a){text-decoration:underline;color:var(--text-primary,#263c34)}.note-title{overflow-wrap:anywhere}.small{font-size:calc(12px * var(--ui-font-scale,1))}.history{margin-top:36px}.filters{display:flex;gap:20px;align-items:end;flex-wrap:wrap}.filters>div{flex:1;min-width:160px}.filters label{margin:0 0 8px}.entries{list-style:none;padding:0;display:grid;gap:12px}.entry{width:100%;text-align:left;display:flex;gap:20px;align-items:center;color:var(--text-primary,#263c34)}.entry strong{flex:1;overflow-wrap:anywhere}.entry time,.entry span{font-size:calc(12px * var(--ui-font-scale,1));color:var(--text-muted,#586d60)}.pagination{justify-content:flex-end;font-size:calc(13px * var(--ui-font-scale,1))}dialog{max-width:440px;width:calc(100% - 40px);padding:26px;border:1px solid #d7dfd5;border-radius:14px;color:var(--text-primary,#263c34)}dialog p{line-height:1.8;font-size:calc(14px * var(--ui-font-scale,1))}dialog::backdrop{background:rgb(30 50 40 / 35%)}@media(max-width:960px){.writing-grid{grid-template-columns:1fr}}@media(max-width:480px){.entry{flex-direction:column;align-items:flex-start;gap:8px}}

/* Directory and document navigation stay beside a bounded editor. */
.folder-sidebar{max-height:calc(100dvh - 40px);overflow:auto;scrollbar-gutter:stable;overscroll-behavior:contain}
.folder-sidebar nav[aria-label="文件夹分类"]{max-height:180px;overflow:auto}
.folder-sidebar .history{margin-top:20px;padding-top:18px;border-top:1px solid #ffffffa0}
.folder-sidebar .history h2{font-size:calc(14px * var(--ui-font-scale,1));overflow-wrap:anywhere;margin-bottom:14px}
.folder-sidebar .filters{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:0;background:none;border:0;box-shadow:none}
.folder-sidebar .filters>div{grid-column:1 / -1;min-width:0}.folder-sidebar .filters input{padding:9px 10px}.folder-sidebar .filters .check{font-size:calc(12px * var(--ui-font-scale,1));margin:0}.folder-sidebar .filters .quiet{padding:7px 12px;font-size:calc(12px * var(--ui-font-scale,1))}
.folder-sidebar .entries{gap:8px;margin:14px 0}.folder-sidebar .entry{display:flex;flex-direction:column;align-items:flex-start;gap:5px;padding:12px;border:1px solid #ffffff8f;border-radius:10px;background:#ffffff38;color:var(--text-primary,#263c34);text-align:left}
.folder-sidebar .entry.current{background:#dceee3b8;border-color:#76a48a}.folder-sidebar .entry strong{font-size:calc(13px * var(--ui-font-scale,1));line-height:1.6}.folder-sidebar .entry span,.folder-sidebar .entry time{font-size:calc(11px * var(--ui-font-scale,1));line-height:1.5}.folder-sidebar .pagination{justify-content:flex-start;gap:8px;margin-top:12px}.folder-sidebar .pagination>span{width:100%;font-size:calc(12px * var(--ui-font-scale,1))}.folder-sidebar .pagination .quiet{padding:7px 10px;font-size:calc(12px * var(--ui-font-scale,1))}
.notes-content .editor-panel{height:clamp(420px,calc(100dvh - 280px),900px);overflow:auto;overscroll-behavior:contain;overflow-anchor:none;scrollbar-gutter:stable}
.notes-content textarea{min-height:240px;height:32dvh;max-height:55dvh}.notes-content .writing-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr))}.notes-content .writing-grid .markdown-preview{max-height:55dvh}
.notes-content .editor-panel .buttons{position:sticky;bottom:-1px;padding:12px 0;background:rgba(245,250,245,.92);backdrop-filter:blur(8px);border-radius:8px}
@media(max-width:1100px){.folder-sidebar{max-height:48dvh;position:static}.notes-content .editor-panel{height:auto;max-height:80dvh}.folder-sidebar nav[aria-label="文件夹分类"]{max-height:160px}}
</style>
