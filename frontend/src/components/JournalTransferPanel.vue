<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useJournalStorage } from '../stores/journalStorage'
import { cloudJournalTransport, removeMigratedCloudCopy } from '../api/journals'
import { errorMessage } from '../api/client'
import { createJournalStorage } from '../services/journalStorage'
import { LocalDirectoryError } from '../services/localJournalStorage'
import { cloudTransferItem, copyAndVerify, matchingEntry, parseImportFile, previewTransfers, sourceDigest, verifyBeforeCleanup } from '../services/journalTransfer'
import type { TransferItem, TransferRecord } from '../types/journalTransfer'
import type { JournalSummary } from '../types/journal'

const props = defineProps<{ locked?: boolean }>()
const emit = defineEmits<{ busyChange: [value: boolean] }>()
const auth = useAuthStore(), directory = useJournalStorage(), ownerId = auth.user?.id
const items = ref<TransferItem[]>([]), errors = ref<string[]>([]), notice = ref(''), busy = ref(false), previewed = ref(false)
const cloudRows = ref<JournalSummary[]>([]), selected = ref<string[]>([]), cloudPage = ref(1), cloudTotal = ref<number | null>(null)
const progress = ref<(TransferRecord & { check: string })[]>([])
const cleanupDialog = ref<HTMLDialogElement | null>(null), cleanupItem = ref<TransferItem | null>(null), confirmed = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const connected = computed(() => directory.state.value.status === 'ready')
const cloudPages = computed(() => Math.max(1, Math.ceil((cloudTotal.value || 0) / 20)))
let active = true, epoch = 0
const valid = () => active && !!ownerId && ownerId === auth.user?.id
const legacy = createJournalStorage('cloud', cloudJournalTransport, { purpose: 'legacy-migration', isCurrent: valid })
const zone = () => auth.user?.timezone || 'Asia/Shanghai'
const labels = { needs_date: '待指定日期', ready: '可复制', conflict: '存在冲突', verified: '本地已验证', error: '未处理成功' }
const detail = (error: unknown) => error instanceof LocalDirectoryError ? error.message : errorMessage(error)
function failedItem(origin: 'file' | 'cloud', label: string, message: string, date = ''): TransferItem {
  const now = new Date().toISOString()
  return { key: `failed:${crypto.randomUUID()}`, origin, label, entry: { id: '', entry_date: date, title: '', content: '', revision: '', created_at: now, updated_at: now }, timezone: zone(), preserveMetadata: true, sourceHash: '', status: 'error', parseError: message, message, serverState: origin === 'cloud' ? 'unknown' : 'not_applicable' }
}
const recordKey = (item: TransferItem) => `${item.key}:${item.entry.entry_date}`
function context() { const version = epoch, binding = directory.state.value.bindingVersion; return () => valid() && epoch === version && binding === directory.state.value.bindingVersion }
function reset() { ++epoch; items.value = []; progress.value = []; cloudRows.value = []; selected.value = []; cloudTotal.value = null; errors.value = []; notice.value = ''; previewed.value = false; cleanupDialog.value?.close(); cleanupItem.value = null; busy.value = false; if (fileInput.value) fileInput.value.value = '' }
watch(() => auth.user?.id, reset, { flush: 'sync' })
watch(() => directory.state.value.bindingVersion, reset, { flush: 'sync' })
watch(busy, value => emit('busyChange', value), { flush: 'sync' })
async function execute(action: (current: () => boolean) => Promise<void>, needDirectory = true) {
  if (!valid() || busy.value || props.locked || (needDirectory && !connected.value)) return
  const current = context(); busy.value = true; errors.value = []; notice.value = ''
  try { await action(current) }
  catch (error) { if (current()) errors.value.push(detail(error)) }
  finally { if (current()) busy.value = false }
}
async function selectFiles(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files || [])
  await execute(async current => {
    if (files.length > 100 || files.reduce((size, file) => size + file.size, 0) > 50 * 1024 * 1024) throw new LocalDirectoryError('INVALID_FILE', '每批最多 100 个文件、合计 50 MiB，请分批导入。')
    const rows: TransferItem[] = []
    for (const file of files) {
      try { rows.push(await parseImportFile(file, zone())) }
      catch (error) { if (current()) rows.push(failedItem('file', file.name, detail(error))) }
      if (!current()) return
    }
    items.value = rows; previewed.value = false
    await previewTransfers(items.value, directory.local(zone))
    if (current()) previewed.value = true
  })
  if (fileInput.value) fileInput.value.value = ''
}
async function preview() { await execute(async current => { await previewTransfers(items.value, directory.local(zone)); if (current()) previewed.value = true }) }
async function loadCloud(page = cloudPage.value) {
  await execute(async current => {
    const result = await legacy.list({ page, page_size: 20 })
    if (current()) { cloudRows.value = result.items; cloudTotal.value = result.total; cloudPage.value = page; selected.value = [] }
  }, false)
}
async function prepareCloud() {
  await execute(async current => {
    const rows: TransferItem[] = []
    for (const summary of cloudRows.value.filter(item => selected.value.includes(item.id))) {
      try {
        const entry = (await legacy.getDay(summary.entry_date)).entry
        if (!current()) return
        if (!entry || entry.revision !== summary.revision || entry.id !== summary.id) throw new LocalDirectoryError('FILE_CONFLICT', '云端版本已改变，请重新加载列表。')
        rows.push(await cloudTransferItem(entry, zone()))
      } catch (error) { if (current()) rows.push(failedItem('cloud', summary.title || summary.entry_date, detail(error), summary.entry_date)) }
    }
    if (!current()) return
    items.value = rows; previewed.value = false
    await previewTransfers(items.value, directory.local(zone))
    if (current()) previewed.value = true
  })
}
function transferRecord(item: TransferItem, state: TransferRecord['state'] = 'verified'): TransferRecord {
  return { key: recordKey(item), origin: item.origin, sourceHash: item.sourceHash, sourceRevision: item.origin === 'cloud' ? item.entry.revision : '', targetDate: item.entry.entry_date, localRevision: item.localRevision!, verifiedAt: new Date().toISOString(), state }
}
async function copy() {
  if (!previewed.value) return
  await execute(async current => {
    const local = directory.local(zone), ledger = directory.progress()
    let success = 0
    for (const item of items.value) {
      if (!current()) return
      if (!['ready', 'verified'].includes(item.status)) continue
      try {
        await copyAndVerify(item, local)
        if (!current()) return
        await ledger.save(transferRecord(item, item.serverState === 'removed' ? 'cloud_removed' : 'verified'))
        if (!current()) return
        item.progressRecorded = true
        success++
      } catch (error) {
        if (!current()) return
        item.status = 'error'; item.progressRecorded = false; item.message = `${detail(error)} 本地可能已有副本，请重新预览；没有清理来源。`
      }
    }
    if (current()) { notice.value = `${success} 篇已完成本地校验并记录进度；原文件与云端副本均保留。冲突或失败项可处理后重新预览。`; window.dispatchEvent(new Event('focusnest-journal-changed')) }
  })
}
async function readProgress() {
  await execute(async current => {
    const data = await directory.progress().read(), local = directory.local(zone)
    const rows: typeof progress.value = []
    for (const record of data.records) {
      let check = '本地文件不存在'
      try { const entry = (await local.getDay(record.targetDate)).entry; check = entry ? entry.revision === record.localRevision ? '本地版本仍一致' : '本地已修改，禁止直接清理云端' : check }
      catch { check = '本地不可读，请检查格式或权限' }
      if (!current()) return
      rows.push({ ...record, check })
    }
    if (current()) { progress.value = rows; notice.value = '进度来自当前目录；未自动读取云端。云端状态仅表示上次记录。' }
  })
}
async function restoreCloud() {
  await execute(async current => {
    const ledger = directory.progress(), data = await ledger.read(), local = directory.local(zone)
    const pending = data.records.filter(item => item.origin === 'cloud' && item.state === 'verified').slice(0, 100)
    const rows: TransferItem[] = []
    for (const record of pending) {
      if (!current()) return
      try {
        const localDocument = await local.readDocument(record.targetDate), localEntry = localDocument?.entry
        if (!localEntry || localEntry.revision !== record.localRevision || await sourceDigest(localEntry) !== record.sourceHash) throw new LocalDirectoryError('FILE_CONFLICT', '本地副本已改变，不能恢复清理资格。')
        const source = (await legacy.getDay(record.targetDate)).entry
        if (!current()) return
        if (!source) { await ledger.save({ ...record, state: 'cloud_removed' }); continue }
        const item = await cloudTransferItem(source, localDocument!.timezone)
        if (record.key !== recordKey(item) || record.sourceHash !== item.sourceHash || !matchingEntry(source, localEntry, true)) throw new LocalDirectoryError('FILE_CONFLICT', '云端原件已改变，请重新选择迁移。')
        item.status = 'verified'; item.localRevision = localEntry.revision; item.progressRecorded = true; item.message = '进度恢复并重新核对本地及云端，云端副本仍存在'
        rows.push(item)
      } catch (error) { if (current()) errors.value.push(`${record.targetDate}：${detail(error)}`) }
    }
    if (current()) { items.value = rows; previewed.value = true; notice.value = '已恢复最多 100 篇未清理的云端迁移检查；没有覆盖本地文件或删除云端。' }
  })
}
function requestCleanup(item: TransferItem) {
  if (props.locked || busy.value || item.status !== 'verified' || !item.localRevision || !item.progressRecorded) return
  cleanupItem.value = item; confirmed.value = false; errors.value = []; cleanupDialog.value?.showModal()
}
async function cleanup() {
  const item = cleanupItem.value
  if (!item || !confirmed.value) return
  await execute(async current => {
    const local = directory.local(zone), ledger = directory.progress()
    const record = (await ledger.read()).records.find(value => value.key === recordKey(item))
    if (!record || record.localRevision !== item.localRevision || record.sourceHash !== item.sourceHash) throw new LocalDirectoryError('INVALID_FILE', '请先记录本地迁移进度，再清理云端。')
    const { missing, ...payload } = await verifyBeforeCleanup(item, local, async () => (await legacy.getDay(item.entry.entry_date)).entry)
    if (!current()) return
    if (!missing) await removeMigratedCloudCopy(item.entry.entry_date, payload)
    if (!current()) return
    item.serverState = 'removed'; item.message = '云端在线副本已不存在；本地文件保留。备份及日志不在此次清理范围。'
    await ledger.save(transferRecord(item, 'cloud_removed'))
    if (current()) { notice.value = item.message; cleanupDialog.value?.close(); cleanupItem.value = null }
  })
}
function invalidate() { previewed.value = false }
function beforeUnload(event: BeforeUnloadEvent) { if (busy.value) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(() => !busy.value)
onUnmounted(() => { active = false; reset(); emit('busyChange', false); window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <details class="panel transfer-panel"><summary>导入 Markdown 日记 / 迁移历史云端日记</summary>
    <p class="muted">先预览，再复制并读回校验。不会覆盖已有不同内容，也不会自动删除任何来源。请先保存或放弃编辑器中的草稿。</p>
    <p v-if="!connected" class="form-error">请先绑定本地目录并授权，不能把导入文件上传到服务器代替。</p>
    <div class="actions"><input ref="fileInput" type="file" accept=".md" multiple hidden @change="selectFiles"><button class="quiet" :disabled="busy || locked || !connected" @click="fileInput?.click()">选择 Markdown 日记文件</button><button class="quiet" :disabled="busy || locked" @click="loadCloud(1)">主动加载历史云端日记</button></div>
    <p class="muted">每批最多 100 个文件、合计 50 MiB；单文件最多 1 MiB。普通 Markdown 可手动指定日期；平台日记保留标题、正文、时区和时间元信息。</p>
    <template v-if="cloudTotal !== null"><h3>历史云端记录 · {{ cloudTotal }} 篇</h3><div class="actions"><button class="quiet" :disabled="busy || locked" @click="selected = cloudRows.map(row => row.id)">选择本页</button><button class="quiet" :disabled="busy || locked || !selected.length || !connected" @click="prepareCloud">预览所选云端迁移</button></div>
      <ul class="cloud-list"><li v-for="row in cloudRows" :key="row.id"><label><input v-model="selected" type="checkbox" :value="row.id" :disabled="busy || locked">{{ row.entry_date }} · {{ row.title || '这一天的记录' }}</label></li></ul>
      <div class="actions"><span>{{ cloudPage }} / {{ cloudPages }}</span><button class="quiet" :disabled="busy || locked || cloudPage <= 1" @click="loadCloud(cloudPage - 1)">上一页云端记录</button><button class="quiet" :disabled="busy || locked || cloudPage >= cloudPages" @click="loadCloud(cloudPage + 1)">下一页云端记录</button></div>
    </template>
    <p v-if="busy" role="status">正在逐篇处理，请等待；可以在完成后重试失败项。</p><p v-if="notice" class="form-success" role="status">{{ notice }}</p><ul v-if="errors.length" class="form-error" role="alert"><li v-for="(error, index) in errors" :key="index">{{ error }}</li></ul>
    <div v-if="items.length" class="preview-table"><h3>迁移预览 / 逐篇结果</h3><p class="muted">更改日期或标题后必须重新预览。冲突项会跳过，可以移除重复项后重试。</p>
      <table><thead><tr><th>来源</th><th>日期与标题</th><th>目标与校验</th><th>操作</th></tr></thead><tbody><tr v-for="(item, index) in items" :key="index"><td>{{ item.origin === 'cloud' ? '云端' : '本地文件' }}<br>{{ item.label }}</td><td><label>导入日期<input v-model="item.entry.entry_date" type="date" min="1000-01-01" max="9999-12-31" :disabled="busy || locked || item.preserveMetadata" @change="invalidate"></label><label>导入标题<input v-model="item.entry.title" maxlength="400" :disabled="busy || locked || item.preserveMetadata" @input="invalidate"></label></td><td>{{ item.entry.entry_date ? `${item.entry.entry_date.slice(0,4)}/${item.entry.entry_date.slice(5,7)}/${item.entry.entry_date}.md` : '请指定日期' }}<p>{{ labels[item.status] }} · {{ item.message }}</p><p v-if="item.origin === 'cloud'">云端在线副本：{{ item.serverState === 'removed' ? '已不存在' : item.serverState === 'unknown' ? '尚未确认' : '仍保留（清理前会重新检查）' }}</p></td><td><button class="quiet" :disabled="busy || locked" @click="items.splice(index, 1); invalidate()">从本批移除</button><button v-if="item.origin === 'cloud' && item.status === 'verified' && item.progressRecorded && item.serverState !== 'removed'" class="quiet" :disabled="busy || locked || !previewed" @click="requestCleanup(item)">单独清理此篇云端副本</button></td></tr></tbody></table>
      <div class="actions"><button class="quiet" :disabled="busy || locked || !connected" @click="preview">重新预览与检查冲突</button><button class="primary-button" :disabled="busy || locked || !connected || !previewed" @click="copy">复制可处理项到本地并校验（保留来源）</button></div>
    </div>
    <h3>本地进度与恢复</h3><p class="muted">逐篇进度写在所选目录的账号专属 JSON 中，仅含日期、来源版本与校验摘要，不含标题正文。文件导入失败可重新选择原文件；云端迁移可恢复检查。</p><div class="actions"><button class="quiet" :disabled="busy || locked || !connected" @click="readProgress">读取本地迁移进度</button><button class="quiet" :disabled="busy || locked || !connected" @click="restoreCloud">恢复未清理的云端迁移检查</button></div>
    <ul><li v-for="record in progress" :key="record.key">{{ record.targetDate }} · {{ record.origin === 'cloud' ? '云端来源' : '文件来源' }} · {{ record.check }} · {{ record.state === 'cloud_removed' ? '上次记录云端已无副本' : '来源未清理 / 本次未检查云端' }}</li></ul>
  </details>
  <dialog ref="cleanupDialog" @cancel.prevent="!busy && cleanupDialog?.close()"><h2>单独清理 {{ cleanupItem?.entry.entry_date }} 的云端副本？</h2><p>提交前将再次读取本地文件并核对云端版本。只清理当前账号的这篇在线数据库记录，不删除本地文件。</p><p>历史备份、数据库日志可能仍有旧数据。本操作不清理备份或日志，不能声称已消除所有历史副本。</p><label><input v-model="confirmed" type="checkbox" :disabled="busy">我已确认保留本地文件，并要清理此篇在线云端副本</label><ul v-if="errors.length" class="form-error"><li v-for="(error,index) in errors" :key="index">{{ error }}</li></ul><div class="actions"><button class="quiet" :disabled="busy" @click="cleanupDialog?.close()">取消，保留云端</button><button class="quiet" :disabled="busy || !confirmed" @click="cleanup">确认清理这一篇云端副本</button></div></dialog>
</template>

<style scoped>
.transfer-panel{display:block;margin:24px 0;padding:24px!important}summary{font-size:calc(18px * var(--ui-font-scale,1));font-weight:600;cursor:pointer}.actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}.quiet{padding:10px 14px;border-radius:8px;font:inherit;cursor:pointer}.primary-button{width:auto;margin:0}.transfer-panel p,dialog p{line-height:1.8}.cloud-list{list-style:none;padding:0}.cloud-list label{display:flex;align-items:center;gap:12px}input[type=checkbox]{width:auto}.preview-table{overflow:auto}table{border-collapse:collapse;width:100%;min-width:760px}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid rgba(127,127,127,.25);overflow-wrap:anywhere}td{max-width:300px}td p{font-size:calc(12px * var(--ui-font-scale,1))}td label{display:block}dialog{max-width:560px;padding:24px;border:0;border-radius:12px;color:var(--text-primary)}
</style>
