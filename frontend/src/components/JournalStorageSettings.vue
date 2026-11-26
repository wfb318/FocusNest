<script setup lang="ts">
import { DEFAULT_JOURNAL_STORAGE_MODE, directoryCapability } from '../services/journalStorage'
import LocalJournalDirectorySettings from './LocalJournalDirectorySettings.vue'
import { useJournalStorage } from '../stores/journalStorage'

defineProps<{ journalPage?: boolean; locked?: boolean }>()
const capability = directoryCapability(window)
const directory = useJournalStorage()
</script>

<template>
  <section class="panel storage-panel" aria-labelledby="journal-storage-title">
    <span class="eyebrow">PRIVACY & STORAGE</span><h2 id="journal-storage-title">日记隐私与存储</h2>
    <p>默认保存方式：<strong>{{ DEFAULT_JOURNAL_STORAGE_MODE === 'local' ? '仅本地文件夹' : '云端' }}</strong></p>
    <p class="muted">连接目录后，可在日记页按日期编辑、保存和搜索本地 Markdown 日记。未连接或失去权限时停止文件操作，不会改用云端保存。</p>
    <details :open="!journalPage || directory.state.value.status !== 'ready'"><summary>目录绑定、权限与隐私说明</summary><dl class="storage-modes">
      <div><dt>仅本地文件夹 <span>默认 · 目录绑定已接入</span></dt><dd>选择真实文件夹，按账号管理绑定。目录和文件内容不上传服务器。</dd></div>
      <div><dt>云端加密保存 <span>单独进入</span></dt><dd>打开加密日记后可按日期读写。确认保存或复制时才发送标题和正文，由服务器加密保存。</dd></div>
      <div><dt>普通云端保存 <span>历史记录只读</span></dt><dd>原有日记可主动查看或复制迁移到本地；不作为新日记的保存位置。</dd></div>
    </dl>
    <p v-if="capability === 'supported'" class="muted">当前浏览器具备目录选择能力。仅在你点击选择或重新授权时请求文件访问权限。</p>
    <p v-else-if="capability === 'insecure'" class="muted">当前环境不满足目录访问所需的安全上下文条件。正式站点需使用 HTTPS，本地开发以浏览器实际支持为准。</p>
    <p v-else class="muted">当前浏览器不支持目录绑定 API。后续将提供手动导入 / 导出方式；不会自动上传到云端。</p>
    <LocalJournalDirectorySettings :locked="locked" />
    <p class="muted">在日记页可导入 Markdown 或主动迁移历史云端日记。复制并读回校验后仍保留来源；清理云端副本需逐篇单独确认。</p>
    <RouterLink v-if="!journalPage" to="/journals">前往日记，主动查看历史云端记录 →</RouterLink>
    </details>
  </section>
</template>

<style scoped>
.storage-panel{margin:24px 0;padding:24px!important}.storage-panel p{line-height:1.8}.storage-modes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin:24px 0}.storage-modes>div{border-left:2px solid currentColor;padding-left:14px;min-width:0}.storage-modes dt{font-weight:600;line-height:1.8}.storage-modes span{display:block;font-size:calc(12px * var(--ui-font-scale,1));font-weight:400;opacity:.75}.storage-modes dd{margin:8px 0 0;font-size:calc(13px * var(--ui-font-scale,1));line-height:1.8}.quiet{padding:10px 14px;border-radius:8px;font:inherit}.small{font-size:calc(12px * var(--ui-font-scale,1))}a{text-decoration:underline;text-underline-offset:4px}@media(max-width:900px){.storage-modes{grid-template-columns:1fr}}
</style>
