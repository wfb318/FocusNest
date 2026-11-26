<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPdfPage } from '../api/documents'
import { errorMessage } from '../api/client'
import type { WorkspaceDocument } from '../types/document'

const props = defineProps<{ document: WorkspaceDocument }>()
const page = ref(1)
const sectionIndex = ref(0)
const imageUrl = ref('')
const loading = ref(false)
const error = ref('')
const section = computed(() => props.document.preview?.sections[sectionIndex.value])
let requestId = 0
let disposed = false
async function loadPage(value: number) {
  const request = ++requestId
  loading.value = true; error.value = ''
  try {
    const blob = await getPdfPage(props.document.id, value)
    if (disposed || request !== requestId) return
    const old = imageUrl.value
    imageUrl.value = URL.createObjectURL(blob); page.value = value
    if (old) URL.revokeObjectURL(old)
  } catch (cause) { if (!disposed && request === requestId) error.value = errorMessage(cause) }
  finally { if (request === requestId) loading.value = false }
}
onMounted(() => { if (props.document.kind === 'pdf') void loadPage(1) })
onUnmounted(() => { disposed = true; ++requestId; if (imageUrl.value) URL.revokeObjectURL(imageUrl.value) })
</script>

<template>
  <div v-if="document.kind === 'pdf'" class="pdf-preview">
    <nav class="page-controls" aria-label="PDF 翻页"><button class="quiet" :disabled="loading || page <= 1" @click="loadPage(page - 1)">上一页</button><span>第 {{ page }} / {{ document.preview?.pages ?? 0 }} 页</span><button class="quiet" :disabled="loading || page >= (document.preview?.pages ?? 0)" @click="loadPage(page + 1)">下一页</button></nav>
    <p v-if="loading" class="muted" role="status">正在生成页面预览…</p><p v-if="error" class="form-error" role="alert">{{ error }} <button class="quiet" :disabled="loading" @click="loadPage(page)">重试</button></p>
    <img v-if="imageUrl && !loading && !error" class="pdf-page" :src="imageUrl" :alt="`PDF 第 ${page} 页`">
    <p class="muted hint">按页显示原始排版。下载原文件可搜索、复制文字或使用本地阅读器。</p>
  </div>
  <div v-else class="office-preview">
    <p class="preview-note">内容预览：展示文字与表格，复杂排版、图片、图表、动画和宏不在预览范围内。Excel 使用文件已有的缓存结果，不执行公式；缓存为空时单元格可能为空。</p>
    <p v-if="document.preview?.truncated" class="form-error">内容较多，预览已按上限截取；完整内容请下载原文件。</p>
    <label for="document-section">{{ document.kind === 'spreadsheet' ? '工作表' : document.kind === 'presentation' ? '幻灯片' : '文档部分' }}</label>
    <select id="document-section" v-model.number="sectionIndex"><option v-for="(item, index) in document.preview?.sections ?? []" :key="index" :value="index">{{ item.title }}</option></select>
    <section v-if="section" class="preview-section" aria-label="Office 内容预览"><h3>{{ section.title }}</h3><p v-for="(paragraph, index) in section.paragraphs" :key="index" class="paragraph">{{ paragraph }}</p><div v-if="section.rows.length" class="table-scroll"><table><tbody><tr v-for="(row, rowIndex) in section.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div><p v-if="!section.rows.length && !section.paragraphs.some(text => text.trim())" class="muted">此部分没有可提取的文字或表格，请下载原文件查看。</p></section>
    <p v-else class="muted">未提取到可读内容，请下载原文件查看。</p>
  </div>
</template>

<style scoped>
.page-controls{display:flex;justify-content:center;align-items:center;gap:16px;margin-bottom:18px;font-size:calc(13px * var(--ui-font-scale,1))}.quiet{padding:8px 12px;border-radius:8px;color:var(--text-primary,#263c34)}.pdf-page{display:block;max-width:100%;height:auto;margin:0 auto;background:white;box-shadow:0 4px 20px #263c3420}.hint,.preview-note{font-size:calc(12px * var(--ui-font-scale,1));line-height:1.8}.preview-note{padding:12px 14px;border-radius:8px;background:#ffffff85;color:var(--text-muted,#586d60)}.office-preview label{display:block;font-size:calc(13px * var(--ui-font-scale,1));margin:18px 0 8px}.office-preview select{width:100%;padding:10px;border:1px solid #b6c9bb;border-radius:8px;color:var(--text-primary,#263c34);background:#ffffffa0}.paragraph{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;font-size:calc(14px * var(--ui-font-scale,1))}.table-scroll{max-width:100%;max-height:55dvh;overflow:auto}table{border-collapse:collapse;background:#ffffff66;font-size:calc(13px * var(--ui-font-scale,1))}td{border:1px solid #b6c9bb;padding:8px;min-width:80px;max-width:420px;white-space:pre-wrap;overflow-wrap:anywhere}
</style>
