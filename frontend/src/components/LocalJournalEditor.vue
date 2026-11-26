<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useJournalStorage } from '../stores/journalStorage'
import { LocalDirectoryError } from '../services/localJournalStorage'
import { createJournalStorage, JournalStorageError } from '../services/journalStorage'
import { encryptedJournalTransport } from '../api/journals'
import { errorMessage } from '../api/client'
import { renderJournalMarkdown } from '../utils/markdown'
import type { Journal, JournalDay, JournalSummary } from '../types/journal'
import type { JournalStorage } from '../types/journalStorage'
import { registerJournalDraftGuard } from '../services/journalDraftGuard'

const emit = defineEmits<{ lockBinding: [locked: boolean] }>()
const props = defineProps<{ externalBusy?: boolean; encrypted?: boolean }>()
const auth = useAuthStore(), directory = useJournalStorage(), ownerId = auth.user?.id
const selectedDate = ref(''), dateInput = ref(''), saved = ref<Journal | null>(null)
const form = reactive({ title: '', content: '' }), ready = ref(false), busy = ref(false), loading = ref(false)
const error = ref(''), notice = ref(''), historyError = ref(''), sourceChanged = ref(false)
const records = ref<JournalSummary[]>([]), total = ref(0), page = ref(1)
const filters = reactive({ start_date: '', end_date: '', q: '' })
const pages = computed(() => Math.max(1, Math.ceil(total.value / 10)))
const dirty = computed(() => form.title !== (saved.value?.title || '') || form.content !== (saved.value?.content || ''))
const localReady = computed(() => directory.state.value.status === 'ready')
const connected = computed(() => props.encrypted || localReady.value)
const preview = computed(() => renderJournalMarkdown(form.content))
const discardDialog = ref<HTMLDialogElement | null>(null), deleteDialog = ref<HTMLDialogElement | null>(null)
const transferDialog = ref<HTMLDialogElement | null>(null)
const transferAction = ref<'save' | 'copy'>('save')
let storage: JournalStorage | undefined, disposed = false, version = 0, historyVersion = 0
let confirmDiscard: ((value: boolean) => void) | undefined
let releaseGuard: (() => void) | undefined
const current = () => !disposed && auth.user?.id === ownerId
const zone = () => auth.user?.timezone || 'Asia/Shanghai'
const cloud = createJournalStorage('cloud_encrypted', encryptedJournalTransport, {
  purpose: 'encrypted-journal', isCurrent: current,
})
const sourceForView = () => props.encrypted ? cloud : directory.local(zone)
const dailyTemplate = '## 今天完成了什么\n\n\n## 今天学到了什么\n\n\n## 遇到了什么问题\n\n\n## 明天准备做什么\n\n'
const message = (cause: unknown) => cause instanceof LocalDirectoryError || cause instanceof JournalStorageError ? cause.message : errorMessage(cause)
watch([dirty, busy], () => emit('lockBinding', dirty.value || busy.value), { immediate: true })
function apply(day: JournalDay) {
  selectedDate.value = day.entry_date; dateInput.value = day.entry_date; saved.value = day.entry
  form.title = day.entry?.title || ''; form.content = day.entry?.content || ''; ready.value = true
}
function resolveDiscard(value: boolean) { discardDialog.value?.close(); confirmDiscard?.(value); confirmDiscard = undefined }
function mayDiscard(): Promise<boolean> {
  if (!dirty.value) return Promise.resolve(true)
  if (confirmDiscard) return Promise.resolve(false)
  return new Promise(resolve => { confirmDiscard = resolve; discardDialog.value?.showModal() })
}
async function openDay(date?: string) {
  if (busy.value || props.externalBusy || !connected.value || !(await mayDiscard()) || !current()) { dateInput.value = selectedDate.value; return }
  const request = ++version
  busy.value = true; error.value = ''; notice.value = ''
  try {
    storage = sourceForView()
    const result = date ? await storage.getDay(date) : await storage.today()
    if (current() && request === version) { apply(result); sourceChanged.value = false; await history() }
  } catch (cause) { if (current() && request === version) error.value = message(cause) }
  finally { if (current() && request === version) busy.value = false }
}
async function history() {
  if (!connected.value || sourceChanged.value) return
  const request = ++historyVersion
  loading.value = true; historyError.value = ''
  try {
    const source = sourceForView()
    const result = await source.list({
      page: page.value, page_size: 10,
      start_date: filters.start_date || undefined, end_date: filters.end_date || undefined,
      q: props.encrypted ? undefined : filters.q || undefined,
    })
    if (!current() || request !== historyVersion) return
    records.value = result.items; total.value = result.total
    if (page.value > pages.value) { page.value = pages.value; await history() }
  } catch (cause) { if (current() && request === historyVersion) { records.value = []; historyError.value = message(cause) } }
  finally { if (request === historyVersion) loading.value = false }
}
function requestSave() {
  if (!props.encrypted) { void save(); return }
  error.value = ''
  transferAction.value = 'save'
  transferDialog.value?.showModal()
}
function requestCopy() {
  if (!saved.value || dirty.value || busy.value || props.externalBusy || sourceChanged.value) return
  error.value = ''
  transferAction.value = 'copy'
  transferDialog.value?.showModal()
}
async function copySaved() {
  const source = storage
  const original = saved.value
  if (!source || !original || !current() || dirty.value || busy.value || props.externalBusy || sourceChanged.value) return
  const request = ++version
  busy.value = true
  error.value = ''; notice.value = ''
  try {
    const localTarget = props.encrypted ? directory.local(zone) : undefined
    const { entry } = await source.getDay(original.entry_date)
    if (!current() || request !== version) return
    if (!entry || entry.revision !== original.revision) {
      throw new LocalDirectoryError('FILE_CONFLICT', '原记录已经改变，请重新载入后再复制。')
    }
    if (localTarget) {
      await localTarget.importEntry(entry, zone())
    } else {
      await cloud.save(entry.entry_date, { title: entry.title, content: entry.content, expected_revision: null })
    }
    if (!current() || request !== version) return
    transferDialog.value?.close()
    notice.value = props.encrypted ? '已复制到本地并校验。云端原件已保留。' : '已复制到云端加密存储并校验。本地原件已保留。'
    if (props.encrypted) window.dispatchEvent(new Event('focusnest-journal-changed'))
  } catch (cause) {
    if (current() && request === version) error.value = message(cause)
  } finally {
    if (current() && request === version) busy.value = false
  }
}
async function save() {
  if (busy.value || props.externalBusy || !ready.value || !storage || sourceChanged.value || !connected.value) return
  const request = ++version, source = storage
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const entry = await source.save(selectedDate.value, { ...form, expected_revision: saved.value?.revision || null })
    if (!current() || request !== version) return
    apply({ entry_date: entry.entry_date, entry })
    transferDialog.value?.close()
    notice.value = props.encrypted ? '已保存云端加密日记，并完成读回校验。' : '已保存到本地文件，并完成读回校验。'
    if (!props.encrypted) window.dispatchEvent(new Event('focusnest-journal-changed'))
    await history()
  } catch (cause) { if (current() && request === version) error.value = message(cause) }
  finally { if (current() && request === version) busy.value = false }
}
async function remove() {
  if (busy.value || props.externalBusy || !saved.value || !storage || sourceChanged.value || !connected.value) return
  const request = ++version, source = storage
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await source.delete(selectedDate.value, saved.value.revision)
    if (!current() || request !== version) return
    apply({ entry_date: selectedDate.value, entry: null }); deleteDialog.value?.close()
    notice.value = props.encrypted ? '云端加密日记已删除。' : '本地日记文件已删除。'
    if (!props.encrypted) window.dispatchEvent(new Event('focusnest-journal-changed'))
    await history()
  } catch (cause) { if (current() && request === version) error.value = message(cause) }
  finally { if (current() && request === version) busy.value = false }
}
watch([() => directory.state.value.bindingVersion, () => directory.state.value.status], (next, previous) => {
  if (props.encrypted) return
  ++version; ++historyVersion; busy.value = false; loading.value = false; records.value = []; total.value = 0
  if (next[0] !== previous[0]) { storage = undefined; sourceChanged.value = true }
  if (!connected.value) {
    if (dirty.value) error.value = '目录或权限不可用，原输入仍保留。可重新授权；更换目录后请先复制输入再重新载入。'
  } else if (!storage || sourceChanged.value) {
    if (dirty.value) error.value = '绑定的目录已改变，原输入仍保留，尚未保存。请先复制需要保留的内容，再重新载入。'
    else void openDay(selectedDate.value || undefined)
  } else { error.value = ''; void history() }
}, { flush: 'sync' })
watch(() => auth.user?.id, () => {
  ++version; ++historyVersion; saved.value = null; form.title = ''; form.content = ''; records.value = []; error.value = ''; notice.value = ''; storage = undefined; resolveDiscard(false)
}, { flush: 'sync' })
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
watch(() => props.externalBusy, (value, previous) => { if (previous && !value && !dirty.value && connected.value) void openDay(selectedDate.value || undefined) })
onBeforeRouteLeave(async () => !current() ? true : busy.value || props.externalBusy ? false : mayDiscard())
onMounted(() => { releaseGuard = registerJournalDraftGuard(async () => !current() ? true : busy.value || props.externalBusy ? false : mayDiscard()); if (connected.value) void openDay(); window.addEventListener('beforeunload', beforeUnload) })
onUnmounted(() => { disposed = true; ++version; ++historyVersion; storage = undefined; resolveDiscard(false); releaseGuard?.(); emit('lockBinding', false); window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <section class="panel local-editor" :aria-label="encrypted ? '加密日记编辑器' : '本地日记编辑器'">
    <div class="heading"><h2>{{ encrypted ? '云端加密日记' : '本地日记' }}</h2><button class="quiet" :disabled="busy || !connected" @click="openDay()">回到今天</button></div>
    <p v-if="!connected" class="muted">目录未连接或权限不可用，请在上方选择目录或重新授权。不会改用云端保存。</p>
    <p v-if="error" role="alert" class="form-error">{{ error }}</p><p v-if="notice" role="status" class="form-success">{{ notice }}</p>
    <div class="heading"><label>记录日期 <input v-model="dateInput" type="date" min="1000-01-01" max="9999-12-31" :disabled="busy || !connected" @change="dateInput && openDay(dateInput)"></label><button class="quiet" :disabled="busy || !connected" @click="openDay(selectedDate || undefined)">{{ encrypted ? '重新载入云端版本' : '重新载入磁盘版本' }}</button></div>
    <template v-if="ready">
      <p class="muted">{{ sourceChanged ? '目录已变化，需重新载入' : dirty ? '有未保存的修改' : saved ? '已载入保存版本' : '这一天尚未记录' }} · {{ auth.user?.timezone }} · <span v-if="encrypted">云端加密</span><span v-else>{{ selectedDate.slice(0, 4) }}/{{ selectedDate.slice(5, 7) }}/{{ selectedDate }}.md</span></p>
      <form @submit.prevent="requestSave"><fieldset :disabled="busy || externalBusy">
        <label for="local-journal-title">日记标题（可选）</label><input id="local-journal-title" v-model="form.title" maxlength="400" placeholder="给今天起个名字">
        <button type="button" class="quiet" :disabled="!!form.content" @click="form.content = dailyTemplate">插入每日回顾模板</button>
        <div class="writing-grid"><div><label for="local-journal-content">正文（Markdown）</label><textarea id="local-journal-content" v-model="form.content" maxlength="200000" rows="18" required :placeholder="encrypted ? '确认后加密保存到服务器' : '保存在你选择的本地文件夹'"></textarea></div><div><h3>预览</h3><article class="preview" v-html="preview"></article></div></div>
        <p v-if="encrypted" class="muted">确认后上传日期、标题和正文。服务器加密保存标题和正文，日期可用于筛选。</p>
        <p v-else class="muted">正文、标题及搜索词在本地处理。保存前会校验内容长度和磁盘版本。</p>
        <div class="actions">
          <button class="primary-button" :disabled="!dirty || !connected || sourceChanged">{{ encrypted ? '保存加密日记' : '保存本地日记' }}</button>
          <button v-if="saved" type="button" class="quiet" :disabled="dirty || sourceChanged || (encrypted && !localReady)" @click="requestCopy">{{ encrypted ? '复制到本地' : '复制到云端加密' }}</button>
          <button v-if="saved" type="button" class="quiet" :disabled="!connected || sourceChanged" @click="deleteDialog?.showModal()">{{ encrypted ? '删除加密日记' : '删除本地日记' }}</button>
        </div>
      </fieldset></form>
    </template>
  </section>
  <section class="panel history" :aria-label="encrypted ? '加密日记列表' : '本地日记列表'"><h2>{{ encrypted ? '回看加密记录' : '回看本地记录' }}</h2>
    <form class="filters" @submit.prevent="page = 1; history()"><label>开始日期<input v-model="filters.start_date" type="date" min="1000-01-01"></label><label>结束日期<input v-model="filters.end_date" type="date" min="1000-01-01"></label><label v-if="!encrypted">本地搜索<input v-model="filters.q" maxlength="100" placeholder="标题或正文关键词"></label><button class="quiet" :disabled="loading || !connected || sourceChanged">{{ encrypted ? '按日期查询' : '查询 / 刷新目录' }}</button></form>
    <p v-if="historyError" role="alert" class="form-error">{{ historyError }}</p><p v-if="loading" class="muted">正在读取记录…</p>
    <p v-else-if="!records.length && !historyError" class="muted">{{ encrypted ? '没有匹配的加密日记。' : connected ? '没有匹配的本地记录。仅识别 YYYY/MM/YYYY-MM-DD.md 中的 FocusNest 日记。' : '请先连接目录。' }}</p>
    <ul><li v-for="entry in records" :key="entry.id"><button class="quiet entry" :disabled="busy || sourceChanged" @click="openDay(entry.entry_date)"><time>{{ entry.entry_date }}</time><strong>{{ entry.title || '这一天的记录' }}</strong></button></li></ul>
    <div class="actions"><span>共 {{ total }} 篇 · {{ page }} / {{ pages }}</span><button class="quiet" :disabled="loading || page <= 1" @click="page--; history()">上一页</button><button class="quiet" :disabled="loading || page >= pages" @click="page++; history()">下一页</button></div>
  </section>
  <dialog ref="discardDialog" @cancel.prevent="resolveDiscard(false)"><h2>放弃未保存的输入？</h2><p>输入仅在当前页面中。可先复制保留，再重新载入或离开。</p><div class="actions"><button class="quiet" autofocus @click="resolveDiscard(false)">保留输入</button><button class="quiet" @click="resolveDiscard(true)">放弃并继续</button></div></dialog>
  <dialog ref="deleteDialog" @cancel.prevent="!busy && deleteDialog?.close()"><h2>删除 {{ selectedDate }} 的{{ encrypted ? '加密' : '本地' }}日记？</h2><p>{{ encrypted ? '将删除此日期的云端加密记录。' : '将删除磁盘中的对应 Markdown 文件。' }}此操作无法通过 FocusNest 撤销。</p><p v-if="error" class="form-error">{{ error }}</p><div class="actions"><button class="quiet" :disabled="busy" @click="deleteDialog?.close()">取消</button><button class="quiet" :disabled="busy" @click="remove">{{ encrypted ? '确认删除云端记录' : '确认删除本地文件' }}</button></div></dialog>
  <dialog ref="transferDialog" @cancel.prevent="!busy && transferDialog?.close()">
    <h2>{{ transferAction === 'save' ? '保存到云端加密存储？' : encrypted ? '复制到本地目录？' : '复制到云端加密存储？' }}</h2>
    <p v-if="encrypted && transferAction === 'copy'">会将 {{ selectedDate }} 的标题和正文写入所选目录。目标日期已有文件时停止，云端原件保留。</p>
    <p v-else>确认后将 {{ selectedDate }} 的标题和正文发送给服务器加密保存。<span v-if="transferAction === 'copy'">目标日期已有加密记录时停止，本地原件保留。</span></p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <div class="actions">
      <button class="quiet" autofocus :disabled="busy" @click="transferDialog?.close()">取消</button>
      <button class="quiet" :disabled="busy" @click="transferAction === 'save' ? save() : copySaved()">{{ transferAction === 'save' ? '确认加密保存' : '确认复制' }}</button>
    </div>
  </dialog>
</template>

<style scoped>
.local-editor,.history{margin-top:24px;padding:24px!important}.heading,.actions{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.actions{justify-content:flex-start;margin-top:18px}.quiet{padding:10px 14px;border-radius:8px;font:inherit;cursor:pointer}.writing-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:20px}.writing-grid>div{min-width:0}.writing-grid textarea{width:100%;box-sizing:border-box;padding:14px;resize:vertical;font:inherit;line-height:1.8}.preview{max-height:560px;overflow:auto;overflow-wrap:anywhere;line-height:1.9}.preview :deep(pre),.preview :deep(table){overflow:auto;display:block}fieldset{border:0;padding:0;min-width:0}.filters{display:grid;grid-template-columns:1fr 1fr 1.5fr auto;gap:12px;align-items:end}ul{list-style:none;padding:0}.entry{width:100%;display:flex;gap:20px;text-align:left;margin-top:10px}.entry strong{overflow-wrap:anywhere}.primary-button{width:auto;margin:0}dialog{max-width:480px;padding:24px;border:0;border-radius:12px;color:var(--text-primary)}p{line-height:1.8}@media(max-width:960px){.writing-grid{grid-template-columns:1fr}.filters{grid-template-columns:1fr 1fr}}
</style>
