<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import JournalStorageSettings from '../components/JournalStorageSettings.vue'
import LegacyJournalPreview from '../components/LegacyJournalPreview.vue'
import LocalJournalEditor from '../components/LocalJournalEditor.vue'
import JournalTransferPanel from '../components/JournalTransferPanel.vue'

const auth = useAuthStore()
const showLegacy = ref(false)
const bindingLocked = ref(false)
const transferBusy = ref(false)
const encrypted = ref(false)
watch(() => auth.user?.id, () => { showLegacy.value = false; encrypted.value = false }, { flush: 'sync' })
</script>

<template>
  <header class="page-header"><div><span class="eyebrow">A LITTLE SPACE TO REFLECT</span><h1>日记</h1><p class="muted">为日记建立只属于你选择的本地目录。</p></div></header>
  <JournalStorageSettings journal-page :locked="bindingLocked || transferBusy" />
  <div v-if="auth.user" class="journal-modes">
    <button class="quiet" :aria-pressed="!encrypted" :disabled="bindingLocked || transferBusy" @click="encrypted = false">仅本地</button>
    <button class="quiet" :aria-pressed="encrypted" :disabled="bindingLocked || transferBusy" @click="encrypted = true; showLegacy = false">打开云端加密日记</button>
    <p class="muted">保存或放弃当前输入后可切换视图。两个位置的记录可以逐篇复制。</p>
  </div>
  <LocalJournalEditor v-if="auth.user" :key="`${auth.user.id}-${encrypted}`" :encrypted="encrypted" :external-busy="transferBusy" @lock-binding="bindingLocked = $event" />
  <JournalTransferPanel v-if="auth.user && !encrypted" :key="`transfer-${auth.user.id}`" :locked="bindingLocked" @busy-change="transferBusy = $event" />
  <section v-if="!showLegacy && !encrypted" class="panel legacy-entry" aria-labelledby="legacy-entry-title">
    <h2 id="legacy-entry-title">以前在这里写过日记？</h2>
    <p class="muted">此入口只读查看历史云端日记；迁移请展开上方导入与迁移面板。只有主动点击后才会读取历史记录。</p>
    <button class="quiet" :disabled="!auth.user" @click="showLegacy = true">查看历史云端日记（只读）</button>
  </section>
  <LegacyJournalPreview v-if="showLegacy && auth.user && !encrypted" :key="auth.user.id" @close="showLegacy = false" />
</template>

<style scoped>
h1{margin:12px 0}.legacy-entry{margin:24px 0;padding:24px!important}.legacy-entry p{line-height:1.8}.quiet{padding:10px 14px;border-radius:8px;font:inherit;cursor:pointer}
.journal-modes{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.journal-modes [aria-pressed="true"]{font-weight:700;outline:1px solid currentColor}
</style>
