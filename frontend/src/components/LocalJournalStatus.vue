<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useJournalStorage } from '../stores/journalStorage'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ date: string; refreshKey: string }>()
const directory = useJournalStorage(), auth = useAuthStore()
const title = ref(''), status = ref('未连接'), description = ref('请先在日记页连接本地目录。')
let version = 0, disposed = false
async function load() {
  const request = ++version, owner = auth.user?.id
  title.value = ''
  if (directory.state.value.status !== 'ready' || !owner) { status.value = '未连接'; description.value = '目录未连接或权限不可用，尚不能判断今天是否已写。'; return }
  status.value = '检查中'; description.value = '正在本地读取今天的记录，不上传日记信息。'
  try {
    const result = await directory.local(() => auth.user?.timezone || 'Asia/Shanghai').getDay(props.date)
    if (disposed || request !== version || owner !== auth.user?.id) return
    title.value = result.entry?.title || ''
    status.value = result.entry ? '已记录' : '尚未记录'
    description.value = result.entry ? title.value || '今天的想法已保存在本地。' : '今天的本地日记还没有创建。'
  } catch {
    if (!disposed && request === version) { title.value = ''; status.value = '暂不可读'; description.value = '请检查本地目录、文件格式或权限；没有改用云端。' }
  }
}
watch([() => props.date, () => props.refreshKey, () => directory.state.value.bindingVersion, () => directory.state.value.status, () => auth.user?.id], () => { void load() }, { immediate: true, flush: 'sync' })
window.addEventListener('focusnest-journal-changed', load)
onUnmounted(() => { disposed = true; ++version; title.value = ''; window.removeEventListener('focusnest-journal-changed', load) })
</script>
<template><section class="panel stat"><span class="small-label">今日日记 · 仅本地</span><strong class="journal-value">{{ status }}</strong><p class="muted">{{ description }}</p><RouterLink to="/journals">查看 / 编辑本地日记 →</RouterLink></section></template>
<style scoped>
.stat{display:flex;flex-direction:column;align-items:flex-start;padding:24px!important;min-width:0;overflow-wrap:anywhere}.journal-value{font-size:calc(24px * var(--ui-font-scale,1));font-weight:500;margin:22px 0 6px}.stat p{font-size:calc(12px * var(--ui-font-scale,1));line-height:1.8}.stat a{margin-top:auto;font-size:calc(13px * var(--ui-font-scale,1));text-decoration:underline}
</style>
