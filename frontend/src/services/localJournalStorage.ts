import type { DirectoryBindings, DirectoryState, JournalDirectoryHandle, LocalFileHandle, LocalFileSnapshot } from '../types/localJournal'

export class LocalDirectoryError extends Error {
  constructor(public readonly code: 'SESSION_CHANGED' | 'PERMISSION_REQUIRED' | 'FILE_CONFLICT' | 'INVALID_FILE' | 'LOCKS_UNAVAILABLE' | 'VERIFY_FAILED' | 'DIRECTORY_UNBOUND', message: string) {
    super(message); this.name = 'LocalDirectoryError'
  }
}
export type DirectoryLock = <T>(operation: () => Promise<T>) => Promise<T>
export function directoryLock<T>(operation: () => Promise<T>): Promise<T> {
  if (!navigator.locks) return Promise.reject(new LocalDirectoryError('LOCKS_UNAVAILABLE', '当前浏览器缺少多标签页写入锁，暂不能写入文件。'))
  // One lock across accounts and directories also covers users selecting the same folder.
  return navigator.locks.request('focusnest-local-journal-files', operation)
}
export function emptyDirectoryState(signedIn = false): DirectoryState {
  return { bindingVersion: 0, status: signedIn ? 'unbound' : 'signed_out', directoryName: '', busy: false, error: '', notice: '', probeName: '', probeDraft: '', probeSaved: false }
}
function current(check: () => boolean) {
  if (!check()) throw new LocalDirectoryError('SESSION_CHANGED', '账号或目录已切换，请重新操作。')
}
function validName(name: string) {
  // Single-file primitives never accept absolute paths or traverse outside the handle.
  if (!name || name.length > 200 || /[\\/:*?"<>|\x00-\x1f]/.test(name) || name === '.' || name === '..' || /[. ]$/.test(name)) {
    throw new LocalDirectoryError('INVALID_FILE', '文件名无效，不能包含目录路径。')
  }
}
async function permitted(handle: JournalDirectoryHandle, check: () => boolean) {
  current(check)
  const permission = await handle.queryPermission({ mode: 'readwrite' })
  current(check)
  if (permission !== 'granted') throw new LocalDirectoryError('PERMISSION_REQUIRED', '目录权限尚未授予或已失效，请点击重新授权。')
}
async function snapshot(file: LocalFileHandle): Promise<LocalFileSnapshot> {
  const value = await file.getFile()
  if (value.size > 1024 * 1024) throw new LocalDirectoryError('INVALID_FILE', '文件超过当前本地读写接口的 1 MiB 限制。')
  const bytes = await value.arrayBuffer()
  let text: string
  try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes) }
  catch { throw new LocalDirectoryError('INVALID_FILE', '文件不是有效 UTF-8，未修改原文件。') }
  const hash = await crypto.subtle.digest('SHA-256', bytes)
  return { text, revision: Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('') }
}
function conflict(): never { throw new LocalDirectoryError('FILE_CONFLICT', '文件已被其他页面或编辑器修改。你的输入仍保留，请先重新读取磁盘内容再决定。') }
function notFound(error: unknown) { return error instanceof Error && error.name === 'NotFoundError' }

export async function readLocalFile(handle: JournalDirectoryHandle, name: string, check: () => boolean): Promise<LocalFileSnapshot> {
  validName(name); await permitted(handle, check)
  const file = await handle.getFileHandle(name)
  current(check)
  const result = await snapshot(file)
  current(check)
  return result
}

export async function writeLocalFile(handle: JournalDirectoryHandle, name: string, text: string, expectedRevision: string | null, check: () => boolean, lock: DirectoryLock = directoryLock): Promise<LocalFileSnapshot> {
  validName(name)
  if (new TextEncoder().encode(text).byteLength > 1024 * 1024) throw new LocalDirectoryError('INVALID_FILE', '内容超过当前本地文件大小限制，未写入。')
  return lock(async () => {
    await permitted(handle, check)
    let file: LocalFileHandle
    let existed = true
    try { file = await handle.getFileHandle(name) }
    catch (error) {
      if (!notFound(error)) throw error
      if (expectedRevision !== null) return conflict()
      current(check)
      file = await handle.getFileHandle(name, { create: true }); existed = false
    }
    current(check)
    const before = await snapshot(file)
    current(check)
    if (existed ? before.revision !== expectedRevision : before.text !== '') conflict()
    // Browser staging writes are committed only at close. Abort on stale context/conflict.
    const writer = await file.createWritable({ mode: 'exclusive' })
    try {
      await permitted(handle, check)
      if ((await snapshot(file)).revision !== before.revision) conflict()
      current(check)
      await writer.write(text)
      if ((await snapshot(file)).revision !== before.revision) conflict()
      current(check)
      await writer.close()
    } catch (error) {
      try { await writer.abort() } catch { /* The stream may already be closed. */ }
      throw error
    }
    current(check)
    const result = await snapshot(file)
    current(check)
    if (result.text !== text) throw new LocalDirectoryError('VERIFY_FAILED', '写入后的读回校验未通过，磁盘内容可能已经变化；页面输入仍保留。')
    return result
  })
}

interface Dependencies {
  bindings: DirectoryBindings
  pick(): Promise<JournalDirectoryHandle>
  lock?: DirectoryLock
  changed?(userId: string): void
}
export function createDirectoryController(deps: Dependencies, notify: (value: DirectoryState) => void) {
  let state = emptyDirectoryState(), userId = '', handle: JournalDirectoryHandle | undefined
  let session = new AbortController(), generation = 0, bindingVersion = 0, probeRevision: string | null = null
  const publish = (value: Partial<DirectoryState>) => { state = { ...state, ...value }; notify({ ...state }) }
  function context() {
    const id = userId, version = generation, signal = session.signal
    return { id, signal, valid: () => !!id && userId === id && generation === version && !signal.aborted }
  }
  function report(error: unknown) {
    if (error instanceof LocalDirectoryError) {
      publish({ error: error.message, ...(error.code === 'PERMISSION_REQUIRED' ? { status: 'permission_required' as const } : {}) })
    } else if (error instanceof Error && error.name === 'NotAllowedError') {
      publish({ status: 'permission_required', error: '目录权限被拒绝或已失效，请重新授权或选择文件夹。' })
    } else {
      publish({ status: 'unavailable', error: '目录或文件暂不可用。输入仍保留，请检查目录位置、磁盘和权限后重试。' })
    }
  }
  async function configure(id: string, force = false) {
    if (id === userId && !force) return
    session.abort(); session = new AbortController(); ++generation
    userId = id; handle = undefined; probeRevision = null
    state = { ...emptyDirectoryState(!!id), bindingVersion: ++bindingVersion }; notify({ ...state })
    if (!id) return
    const ctx = context()
    publish({ status: 'restoring', busy: true })
    try {
      const stored = await deps.bindings.load(id, ctx.signal)
      if (!ctx.valid()) return
      if (!stored) { publish({ status: 'unbound' }); return }
      handle = stored
      const permission = await stored.queryPermission({ mode: 'readwrite' })
      if (ctx.valid()) publish({ directoryName: stored.name, status: permission === 'granted' ? 'ready' : 'permission_required' })
    } catch {
      if (ctx.valid()) publish({ status: 'unavailable', error: '无法恢复此账号的目录绑定，请重新选择。不会改用其他账号的目录。' })
    } finally { if (ctx.valid()) publish({ busy: false }) }
  }
  async function choose() {
    if (!userId || state.busy) return
    const ctx = context()
    publish({ busy: true, error: '', notice: '' })
    try {
      // First awaited action is the picker, preserving the browser's click activation.
      const selected = await deps.pick()
      if (!ctx.valid()) return
      const permission = await selected.queryPermission({ mode: 'readwrite' })
      if (!ctx.valid()) return
      let persisted = true
      try { await deps.bindings.save(ctx.id, selected, ctx.signal) }
      catch { persisted = false }
      if (!ctx.valid()) return
      handle = selected; probeRevision = null
      publish({ bindingVersion: ++bindingVersion, status: permission === 'granted' ? 'ready' : 'permission_required', directoryName: selected.name, probeName: '', probeDraft: '', probeSaved: false, notice: persisted ? '目录已绑定到当前账号；尚未写入任何文件。' : '目录仅在本次会话中连接；无法更新浏览器绑定记录，下次请重新确认目录。' })
      if (persisted) deps.changed?.(ctx.id)
    } catch (error) {
      if (ctx.valid()) {
        if (error instanceof Error && error.name === 'AbortError') publish({ notice: '已取消选择，原目录绑定保持不变。' })
        else report(error)
      }
    } finally { if (ctx.valid()) publish({ busy: false }) }
  }
  async function permission(request = false) {
    if (!handle || state.busy || !userId) return
    const ctx = context(), selected = handle
    publish({ busy: true, error: '', notice: '' })
    try {
      // requestPermission must also be called directly from the user's click.
      const value = await (request ? selected.requestPermission({ mode: 'readwrite' }) : selected.queryPermission({ mode: 'readwrite' }))
      if (ctx.valid()) publish({ status: value === 'granted' ? 'ready' : 'permission_required', notice: value === 'granted' ? '目录读写权限有效；尚未验证文件写入。' : '尚未获得读写权限，请主动重新授权或更换文件夹。' })
    } catch (error) { if (ctx.valid()) report(error) }
    finally { if (ctx.valid()) publish({ busy: false }) }
  }
  async function unbind() {
    if (!userId || state.busy) return
    const ctx = context()
    publish({ busy: true, error: '', notice: '' })
    try {
      await deps.bindings.remove(ctx.id, ctx.signal)
      if (!ctx.valid()) return
      handle = undefined; probeRevision = null
      state = { ...emptyDirectoryState(true), bindingVersion: ++bindingVersion }
      publish({ notice: '已解除当前账号的绑定，磁盘文件没有删除。' }); deps.changed?.(ctx.id)
    } catch { if (ctx.valid()) publish({ error: '浏览器未能移除绑定，尚未解绑，请重试。' }) }
    finally { if (ctx.valid()) publish({ busy: false }) }
  }
  async function probe(saveExisting = false) {
    if (!handle || state.busy || !userId) return
    const ctx = context(), selected = handle
    const name = saveExisting ? state.probeName : `FocusNest-check-${crypto.randomUUID()}.txt`
    if (!name) return
    const text = saveExisting ? state.probeDraft : 'FocusNest 本地目录读写检查\n这是独立测试文件，不是日记，可以自行保留或删除。\n'
    publish({ busy: true, error: '', notice: '', probeName: name, probeDraft: text, probeSaved: false })
    if (!saveExisting) probeRevision = null
    try {
      const result = await writeLocalFile(selected, name, text, probeRevision, ctx.valid, deps.lock)
      if (!ctx.valid()) return
      probeRevision = result.revision
      publish({ status: 'ready', probeSaved: true, notice: '测试文件写入并读回校验通过。文件保留在所选目录，没有上传服务器。' })
    } catch (error) { if (ctx.valid()) report(error) }
    finally { if (ctx.valid()) publish({ busy: false }) }
  }
  async function reloadProbe() {
    if (!handle || !state.probeName || state.busy) return
    const ctx = context(), selected = handle, name = state.probeName
    publish({ busy: true, error: '', notice: '' })
    try {
      const result = await readLocalFile(selected, name, ctx.valid)
      if (!ctx.valid()) return
      // Do not replace a failed-save draft. User can compare/copy the disk text.
      probeRevision = result.revision
      publish({ status: 'ready', notice: '已读取最新磁盘版本；编辑框中的输入未替换。再次保存将以此版本校验。' })
      return result.text
    } catch (error) { if (ctx.valid()) report(error) }
    finally { if (ctx.valid()) publish({ busy: false }) }
  }
  function editProbe(value: string) { if (!state.busy && userId) publish({ probeDraft: value, probeSaved: false }) }
  function connection() {
    const selected = handle, ctx = context()
    if (!selected || state.status !== 'ready') throw new LocalDirectoryError('DIRECTORY_UNBOUND', '目录尚未连接或缺少权限，请先选择目录并授权。')
    return { handle: selected, isCurrent: () => ctx.valid() && handle === selected }
  }
  return { configure, choose, permission, unbind, probe, reloadProbe, editProbe, connection }
}
