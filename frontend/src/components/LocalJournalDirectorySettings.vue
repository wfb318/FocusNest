<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useJournalStorage } from '../stores/journalStorage'
import { directoryCapability } from '../services/journalStorage'
defineProps<{ locked?: boolean }>()

const directory = useJournalStorage(), auth = useAuthStore()
const { state } = directory
const capability = directoryCapability(window)
const hasWriteLocks = !!navigator.locks
const diskText = ref<string | null>(null)
const labels = { signed_out: '请先登录', unbound: '尚未绑定', restoring: '正在恢复绑定', permission_required: '需要重新授权', ready: '已连接', unavailable: '暂不可用' }
const canWrite = computed(() => state.value.status === 'ready' && !!navigator.locks)
watch(() => auth.user?.id, () => { diskText.value = null }, { flush: 'sync' })
watch(() => state.value.probeName, () => { diskText.value = null }, { flush: 'sync' })
async function readDisk() {
  const text = await directory.reloadProbe()
  if (text !== undefined) diskText.value = text
}
</script>

<template>
  <div class="directory-settings" aria-label="本地日记目录绑定">
    <p><strong>目录状态：{{ labels[state.status] }}</strong><span v-if="state.directoryName"> · {{ state.directoryName }}</span></p>
    <p class="muted">绑定按当前浏览器和账号分别保存，不会上传目录名、路径或文件内容。绑定本身不会扫描目录，也不会修改文件。</p>
    <p v-if="locked" class="muted">日记有未保存输入或正在处理文件，请先保存或放弃修改，再更换或解绑目录。</p>
    <div class="actions">
      <button class="quiet" :disabled="locked || state.busy || !auth.user || capability !== 'supported'" @click="directory.choose">{{ state.directoryName ? '更换日记文件夹' : '选择日记文件夹' }}</button>
      <button v-if="state.directoryName" class="quiet" :disabled="state.busy" @click="directory.checkPermission">检查目录权限</button>
      <button v-if="state.status === 'permission_required'" class="quiet" :disabled="state.busy" @click="directory.authorize">重新授权目录读写</button>
      <button v-if="state.directoryName || state.status === 'unavailable'" class="quiet" :disabled="locked || state.busy" @click="directory.unbind">解除绑定（不删文件）</button>
    </div>
    <p v-if="capability !== 'supported'" class="muted">当前浏览器无法绑定真实目录。请使用支持此能力的桌面浏览器；手动导入 / 导出将在后续步骤提供，不会用云端保存替代。</p>
    <p v-if="!hasWriteLocks" class="muted">当前环境缺少多标签页写入锁，目录可以查看状态，文件写入暂不可用。</p>
    <p v-if="state.busy" role="status" class="muted">正在处理目录操作…</p>
    <p v-if="state.error" role="alert" class="form-error">{{ state.error }}</p>
    <p v-if="state.notice" role="status" class="form-success">{{ state.notice }}</p>
    <div v-if="state.directoryName" class="directory-check">
      <h3>验证目录读写</h3>
      <p class="muted">点击后，在所选目录中新建一个随机命名的 FocusNest-check 测试文件并读回校验。文件会保留，不改动已有日记；可用其他编辑器打开测试文件，检查冲突保护。</p>
      <button class="quiet" :disabled="state.busy || !canWrite" @click="directory.probe">生成独立测试文件并验证读写</button>
      <template v-if="state.probeName">
        <p class="muted">测试文件：{{ state.probeName }} · {{ state.probeSaved ? '已写入并校验' : '输入尚未确认写入' }}</p>
        <label for="directory-probe-draft">测试文件内容（仅测试，非日记编辑器）</label>
        <textarea id="directory-probe-draft" :value="state.probeDraft" :disabled="state.busy" maxlength="4000" rows="4" @input="directory.editProbe(($event.target as HTMLTextAreaElement).value)"></textarea>
        <div class="actions"><button class="quiet" :disabled="state.busy || !canWrite" @click="directory.saveProbe">保存测试内容</button><button class="quiet" :disabled="state.busy" @click="readDisk">读取最新磁盘版本（保留输入）</button></div>
        <template v-if="diskText !== null"><h4>磁盘内容对照</h4><pre>{{ diskText }}</pre></template>
      </template>
    </div>
    <p class="muted">正式日记在日记页保存到 YYYY/MM/YYYY-MM-DD.md；这里的测试文件独立于日记。</p>
  </div>
</template>

<style scoped>
.directory-settings{margin-top:20px}.directory-settings p{line-height:1.8;overflow-wrap:anywhere}.actions{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.quiet{padding:10px 14px;border-radius:8px;font:inherit;cursor:pointer}.directory-check{border-top:1px solid rgba(127,127,127,.25);margin-top:22px;padding-top:12px}.directory-check label{display:block;margin:16px 0 8px}.directory-check textarea{width:100%;box-sizing:border-box;resize:vertical;font:inherit;line-height:1.7;padding:12px}.directory-check pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto;font:inherit;line-height:1.7}
</style>
