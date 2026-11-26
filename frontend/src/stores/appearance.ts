import { readonly, ref } from 'vue'
import { prepareBackground } from '../utils/backgroundMedia'
import { DEFAULT_STYLE, normalizeStyle } from '../utils/appearanceStyle'
import type { StylePreferences } from '../utils/appearanceStyle'
import type { BackgroundKind } from '../utils/backgroundMedia'

const backgroundUrl = ref('')
const posterUrl = ref('')
const backgroundKind = ref<BackgroundKind>('image')
const paused = ref(false)
const playbackBlocked = ref(false)
const playbackAttempt = ref(0)
const veil = ref(0.38)
const stylePreferences = ref<StylePreferences>({ ...DEFAULT_STYLE })
const busy = ref(false)
const error = ref('')
const notice = ref('')
// Retain the image key for backwards compatibility with saved image preferences.
type Appearance = { image: Blob | null; veil: number; kind?: BackgroundKind; poster?: Blob | null; paused?: boolean; fontScale?: number; textColor?: string; glassColor?: string }
let initialized: Promise<void> | undefined

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('focusnest-appearance', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('preferences')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    request.onblocked = () => reject(new Error('Storage blocked'))
  })
}
async function storage(write?: Appearance): Promise<Appearance | undefined> {
  const db = await openDatabase()
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction('preferences', write ? 'readwrite' : 'readonly')
      const store = transaction.objectStore('preferences')
      const request = write ? store.put(write, 'workspace') : store.get('workspace')
      transaction.oncomplete = () => resolve(write ?? request.result)
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally { db.close() }
}
function apply(value: Appearance) {
  stylePreferences.value = normalizeStyle(value)
  const previous = backgroundUrl.value
  backgroundUrl.value = value.image instanceof Blob ? URL.createObjectURL(value.image) : ''
  if (posterUrl.value) URL.revokeObjectURL(posterUrl.value)
  posterUrl.value = value.poster instanceof Blob ? URL.createObjectURL(value.poster) : ''
  backgroundKind.value = value.kind ?? (value.image?.type.startsWith('video/') ? 'video' : value.image?.type === 'image/gif' ? 'gif' : 'image')
  paused.value = value.paused ?? window.matchMedia('(prefers-reduced-motion: reduce)').matches
  playbackBlocked.value = false
  veil.value = Number.isFinite(value.veil) ? Math.min(0.8, Math.max(0.1, value.veil)) : 0.38
  if (previous) URL.revokeObjectURL(previous)
}
async function initialize() {
  initialized ??= (async () => {
    try { const value = await storage(); if (value) apply(value) }
    catch { error.value = '无法读取本机外观设置。你仍可以使用默认背景。' }
  })()
  await initialized
}
async function setBackground(file: File) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await initialize()
    const prepared = await prepareBackground(file)
    const value = { ...stylePreferences.value, ...prepared, veil: veil.value, paused: window.matchMedia('(prefers-reduced-motion: reduce)').matches }
    await storage(value); apply(value)
    error.value = ''; notice.value = '背景已更换，并保存在当前浏览器。'
  } catch (cause) { error.value = cause instanceof Error && cause.name === 'Error' ? cause.message : '保存失败，本机存储可能不可用或已满。' }
  finally { busy.value = false }
}
async function saveVeil(value: number) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await initialize()
    const existing = await storage()
    const next = { ...existing, image: existing?.image ?? null, veil: Math.min(0.8, Math.max(0.1, value)) }
    await storage(next); veil.value = next.veil; notice.value = '背景明暗已保存。'
  } catch { error.value = '无法保存外观设置，请检查浏览器存储空间。' }
  finally { busy.value = false }
}
async function savePaused(value: boolean) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await initialize()
    const existing = await storage()
    await storage({ ...existing, image: existing?.image ?? null, veil: veil.value, paused: value })
    paused.value = value; playbackBlocked.value = false; ++playbackAttempt.value
    notice.value = value ? '动态背景已暂停。' : '动态背景已启用。'
  } catch { error.value = '无法保存播放设置，请检查浏览器存储。' }
  finally { busy.value = false }
}
async function saveStyle(value: Partial<StylePreferences>) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await initialize()
    const existing = await storage()
    const normalized = normalizeStyle(value)
    await storage({ ...existing, image: existing?.image ?? null, veil: veil.value, ...normalized })
    stylePreferences.value = normalized
    notice.value = '文字与磨砂样式已保存。'
  } catch { error.value = '无法保存样式，请检查浏览器存储。' }
  finally { busy.value = false }
}
async function reset() {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await initialize()
    const value = { ...stylePreferences.value, image: null, veil: 0.38 }
    await storage(value); apply(value); notice.value = '已恢复默认背景。'
  } catch { error.value = '恢复失败，请检查浏览器存储设置。' }
  finally { busy.value = false }
}
export function useAppearance() {
  return { stylePreferences: readonly(stylePreferences), backgroundUrl: readonly(backgroundUrl), posterUrl: readonly(posterUrl), backgroundKind: readonly(backgroundKind), paused: readonly(paused), playbackBlocked: readonly(playbackBlocked), playbackAttempt: readonly(playbackAttempt), veil: readonly(veil), busy: readonly(busy), error: readonly(error), notice: readonly(notice), initialize, setBackground, saveVeil, savePaused, saveStyle, reset, reportPlaybackBlocked: () => { playbackBlocked.value = true } }
}
