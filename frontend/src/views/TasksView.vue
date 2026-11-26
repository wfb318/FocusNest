<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { completeTask, createTask, deleteTask, getTask, listTasks, updateTask } from '../api/tasks'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { Task, TaskInput, TaskPriority, TaskStatus } from '../types/task'

const auth = useAuthStore()
const items = ref<Task[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const formError = ref('')
const notice = ref('')
const editorOpen = ref(false)
const editingId = ref<string | null>(null)
const titleInput = ref<HTMLInputElement | null>(null)
const deleteDialog = ref<HTMLDialogElement | null>(null)
const deleteTarget = ref<Task | null>(null)
const deleteError = ref('')
const filters = reactive({ today: false, status: '' as TaskStatus | '', priority: '' as TaskPriority | '', scheduled_date: '', due_date: '' })
const form = reactive({ title: '', description: '', status: 'todo' as TaskStatus, priority: 'medium' as TaskPriority, scheduled_date: '', due_date: '', estimated_minutes: '' as string | number })
const statusNames: Record<TaskStatus, string> = { todo: '待办', doing: '进行中', done: '已完成' }
const priorityNames: Record<TaskPriority, string> = { low: '低', medium: '中', high: '高' }
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
let requestId = 0

function todayDate() {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: auth.user?.timezone || 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const value = (type: string) => parts.find(part => part.type === type)?.value
  return `${value('year')}-${value('month')}-${value('day')}`
}

async function load() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const result = await listTasks({ page: page.value, page_size: pageSize, today: filters.today, status: filters.status || undefined, priority: filters.priority || undefined, scheduled_date: filters.scheduled_date || undefined, due_date: filters.due_date || undefined })
    if (current !== requestId) return
    items.value = result.items
    total.value = result.total
    if (page.value > pages.value) { page.value = pages.value; await load() }
  } catch (cause) {
    if (current === requestId) { items.value = []; total.value = 0; error.value = errorMessage(cause) }
  } finally { if (current === requestId) loading.value = false }
}
watch(filters, () => { page.value = 1; void load() }, { immediate: true })
function changePage(value: number) { page.value = value; void load() }
function resetFilters() { Object.assign(filters, { today: false, status: '', priority: '', scheduled_date: '', due_date: '' }) }

async function focusEditor() { await nextTick(); titleInput.value?.focus() }
function startCreate() {
  editingId.value = null
  Object.assign(form, { title: '', description: '', status: 'todo', priority: 'medium', scheduled_date: filters.today ? todayDate() : '', due_date: '', estimated_minutes: '' })
  formError.value = ''; editorOpen.value = true
  void focusEditor()
}
async function edit(task: Task) {
  saving.value = true; error.value = ''; formError.value = ''
  try {
    const detail = await getTask(task.id)
    Object.assign(form, { ...detail, description: detail.description || '', scheduled_date: detail.scheduled_date || '', due_date: detail.due_date || '', estimated_minutes: detail.estimated_minutes ?? '' })
    editingId.value = detail.id; editorOpen.value = true
    saving.value = false
    await focusEditor()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { saving.value = false }
}
async function save() {
  if (!form.title.trim()) { formError.value = '请填写任务标题。'; return }
  const input: TaskInput = { title: form.title.trim(), description: form.description.trim() || null, status: form.status, priority: form.priority, scheduled_date: form.scheduled_date || null, due_date: form.due_date || null, estimated_minutes: form.estimated_minutes === '' ? null : Number(form.estimated_minutes) }
  saving.value = true; formError.value = ''; notice.value = ''
  try {
    if (editingId.value) await updateTask(editingId.value, input)
    else await createTask(input)
    notice.value = '任务已保存。若列表中未显示，请检查当前筛选条件。'
    editorOpen.value = false
    page.value = 1
    await load()
  } catch (cause) { formError.value = errorMessage(cause) }
  finally { saving.value = false }
}
async function toggle(task: Task) {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    if (task.status === 'done') await updateTask(task.id, { status: 'todo' })
    else await completeTask(task.id)
    notice.value = task.status === 'done' ? '任务已恢复为待办。' : '任务已完成。'
    if (editingId.value === task.id) editorOpen.value = false
    await load()
  } catch (cause) { error.value = errorMessage(cause) }
  finally { saving.value = false }
}
function requestDelete(task: Task) {
  deleteTarget.value = task
  deleteError.value = ''
  deleteDialog.value?.showModal()
}
function cancelDelete() {
  if (saving.value) return
  deleteDialog.value?.close()
  deleteTarget.value = null
}
async function remove() {
  const task = deleteTarget.value
  if (!task || saving.value) return
  saving.value = true; error.value = ''; notice.value = ''
  try {
    await deleteTask(task.id)
    if (editingId.value === task.id) editorOpen.value = false
    notice.value = '任务已删除。'
    deleteDialog.value?.close()
    deleteTarget.value = null
    await load()
  } catch (cause) { deleteError.value = errorMessage(cause) }
  finally { saving.value = false }
}
</script>

<template>
  <header class="page-header">
    <div><span class="eyebrow">MAKE ROOM FOR WHAT MATTERS</span><h1>任务</h1><p class="muted">把想做的事写下来，给重要的事留出时间。</p></div>
    <button class="primary-button task-create" :disabled="saving" @click="startCreate">＋ 新建任务</button>
  </header>
  <section v-if="editorOpen" class="panel task-editor" aria-labelledby="editor-title">
    <h2 id="editor-title">{{ editingId ? '任务详情与编辑' : '新建任务' }}</h2>
    <form @submit.prevent="save">
      <fieldset :disabled="saving">
        <label for="task-title">任务标题</label><input id="task-title" ref="titleInput" v-model="form.title" required maxlength="200" placeholder="例如：整理本周的学习笔记">
        <label for="task-description">任务说明（可选）</label><textarea id="task-description" v-model="form.description" rows="3" maxlength="10000" placeholder="记录具体步骤或补充信息"></textarea>
        <div class="task-form-grid">
          <div><label for="task-status">状态</label><select id="task-status" v-model="form.status"><option v-for="(label, key) in statusNames" :key="key" :value="key">{{ label }}</option></select></div>
          <div><label for="task-priority">优先级</label><select id="task-priority" v-model="form.priority"><option v-for="(label, key) in priorityNames" :key="key" :value="key">{{ label }}</option></select></div>
          <div><label for="task-scheduled">计划日期</label><input id="task-scheduled" v-model="form.scheduled_date" type="date"></div>
          <div><label for="task-due">截止日期</label><input id="task-due" v-model="form.due_date" type="date"></div>
          <div><label for="task-estimate">预计耗时（分钟）</label><input id="task-estimate" v-model="form.estimated_minutes" type="number" min="1" max="10080" step="1" placeholder="可选，例如 30"></div>
        </div>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
        <div class="task-buttons"><button class="primary-button task-create" type="submit">{{ saving ? '保存中…' : '保存任务' }}</button><button class="secondary-button" type="button" @click="editorOpen = false">取消</button></div>
      </fieldset>
    </form>
  </section>
  <section class="panel task-filter-panel" aria-label="任务筛选">
    <div class="task-buttons"><button class="secondary-button" :aria-pressed="!filters.today" :disabled="saving" @click="filters.today = false">全部任务</button><button class="secondary-button" :aria-pressed="filters.today" :disabled="saving" @click="filters.today = true">今日任务</button></div>
    <p class="muted">今日按 {{ auth.user?.timezone }} 判断，包含计划在今天或今天截止的任务。</p>
    <div class="task-filters">
      <div><label for="filter-status">状态</label><select id="filter-status" v-model="filters.status" :disabled="saving"><option value="">全部状态</option><option v-for="(label, key) in statusNames" :key="key" :value="key">{{ label }}</option></select></div>
      <div><label for="filter-priority">优先级</label><select id="filter-priority" v-model="filters.priority" :disabled="saving"><option value="">全部优先级</option><option v-for="(label, key) in priorityNames" :key="key" :value="key">{{ label }}</option></select></div>
      <div><label for="filter-scheduled">计划日期</label><input id="filter-scheduled" v-model="filters.scheduled_date" type="date" :disabled="saving"></div>
      <div><label for="filter-due">截止日期</label><input id="filter-due" v-model="filters.due_date" type="date" :disabled="saving"></div>
    </div>
    <div class="task-buttons"><button class="text-button" :disabled="saving" @click="resetFilters">重置筛选</button><button class="text-button" :disabled="loading || saving" @click="load">刷新列表</button></div>
  </section>
  <p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <section :aria-busy="loading" aria-label="任务列表">
    <p v-if="loading" class="muted" role="status">正在加载任务…</p>
    <div v-else-if="!items.length && !error" class="panel task-empty"><h2>这里还没有任务</h2><p class="muted">新建一个任务，或调整筛选条件，开始安排你的下一步。</p></div>
    <ul v-else-if="!loading" class="task-list">
      <li v-for="task in items" :key="task.id" class="panel task-card" :class="{ 'task-done': task.status === 'done' }">
        <div class="task-card-heading"><h2>{{ task.title }}</h2><span class="task-badge" :class="`priority-${task.priority}`">{{ priorityNames[task.priority] }}优先级</span></div>
        <p v-if="task.description" class="task-description">{{ task.description }}</p>
        <div class="task-meta"><span>{{ statusNames[task.status] }}</span><span v-if="task.scheduled_date">计划 {{ task.scheduled_date }}</span><span v-if="task.due_date" :class="{ overdue: task.status !== 'done' && task.due_date < todayDate() }">截止 {{ task.due_date }}</span><span v-if="task.estimated_minutes">预计 {{ task.estimated_minutes }} 分钟</span></div>
        <div class="task-buttons"><button class="secondary-button" :disabled="saving" @click="toggle(task)">{{ task.status === 'done' ? '恢复待办' : '完成任务' }}</button><button class="text-button" :disabled="saving" @click="edit(task)">查看 / 编辑</button><button class="text-button danger" :disabled="saving" @click="requestDelete(task)">删除</button></div>
      </li>
    </ul>
  </section>
  <nav v-if="!error" class="task-pagination" aria-label="任务分页"><span>共 {{ total }} 项 · 第 {{ page }} / {{ pages }} 页</span><div class="task-buttons"><button class="secondary-button" :disabled="page <= 1 || loading || saving" @click="changePage(page - 1)">上一页</button><button class="secondary-button" :disabled="page >= pages || loading || saving" @click="changePage(page + 1)">下一页</button></div></nav>
  <dialog ref="deleteDialog" class="task-delete-dialog" aria-labelledby="delete-title" aria-describedby="delete-description" @cancel.prevent="cancelDelete">
    <h2 id="delete-title">删除任务？</h2>
    <p id="delete-description">确定删除“{{ deleteTarget?.title }}”吗？删除后无法恢复。</p>
    <p v-if="deleteError" class="form-error" role="alert">{{ deleteError }}</p>
    <div class="task-buttons"><button class="secondary-button" autofocus :disabled="saving" @click="cancelDelete">取消删除</button><button class="secondary-button danger" :disabled="saving" @click="remove">{{ saving ? '删除中…' : '确认删除' }}</button></div>
  </dialog>
</template>

<style scoped>
.task-delete-dialog{max-width:440px;width:calc(100% - 40px);border:1px solid #d7dfd5;border-radius:14px;padding:24px;color:var(--text-primary,#263c34);background:#fff}.task-delete-dialog::backdrop{background:rgb(30 50 40 / 35%)}.task-delete-dialog p{font-size:calc(14px * var(--ui-font-scale,1));line-height:1.8;overflow-wrap:anywhere}
.page-header h1{margin-bottom:4px}.task-create{width:auto;margin:0}.task-editor,.task-filter-panel{margin-top:24px}.task-editor fieldset{border:0;padding:0;margin:0;min-width:0}.task-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}select,textarea,.task-filters input{width:100%;min-width:0;border:1px solid #d7dfd5;border-radius:8px;padding:11px 12px;background:#fcfdfb;color:var(--text-primary,#263c34);font:inherit;font-size:calc(14px * var(--ui-font-scale,1))}textarea{resize:vertical}select:focus,textarea:focus{outline:2px solid #7b9f86;outline-offset:2px}.task-buttons{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-top:16px}.secondary-button{background:#fff;border:1px solid #cedbcc;border-radius:8px;color:var(--text-primary,#263c34);padding:9px 14px;font-size:calc(13px * var(--ui-font-scale,1))}.secondary-button[aria-pressed=true]{background:#eaf0e7;border-color:#39765c}.text-button{border:0;background:transparent;color:var(--text-primary,#263c34);padding:8px;font-size:calc(13px * var(--ui-font-scale,1))}.danger,.overdue{color:#ad4141}.task-filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.task-filters label{display:block;font-size:calc(12px * var(--ui-font-scale,1));margin-bottom:8px}.task-list{list-style:none;padding:0;margin:24px 0;display:grid;gap:14px}.task-card{padding:22px 26px}.task-card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.task-card h2{margin:0;overflow-wrap:anywhere;white-space:pre-wrap}.task-badge{white-space:nowrap;font-size:calc(11px * var(--ui-font-scale,1));padding:4px 8px;border-radius:5px;background:#eff2ec;color:var(--text-muted,#586d60)}.priority-high{background:#fbede6;color:#a15c36}.priority-medium{background:#eef1e1;color:#6b713d}.task-description{white-space:pre-wrap;overflow-wrap:anywhere;font-size:calc(14px * var(--ui-font-scale,1));line-height:1.8;color:var(--text-muted,#586d60);max-height:7.2em;overflow:auto}.task-meta{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:calc(12px * var(--ui-font-scale,1));color:var(--text-muted,#586d60);margin-top:14px}.task-done h2{text-decoration:line-through;color:var(--text-muted,#586d60)}.task-pagination{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:calc(13px * var(--ui-font-scale,1));color:var(--text-muted,#586d60);margin-top:20px}.task-pagination .task-buttons{margin:0}.task-empty{text-align:center;margin-top:24px;padding:42px 24px}@media(max-width:850px){.task-filters{grid-template-columns:1fr 1fr}}@media(max-width:480px){.task-form-grid,.task-filters{grid-template-columns:1fr}.task-pagination{align-items:flex-start;flex-direction:column}.task-card{padding:18px}.task-card-heading{flex-wrap:wrap}}
</style>
