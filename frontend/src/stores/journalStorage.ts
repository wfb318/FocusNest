import { readonly, shallowRef } from 'vue'
import { directoryCapability } from '../services/journalStorage'
import { createDirectoryController, emptyDirectoryState } from '../services/localJournalStorage'
import { directoryBindings } from '../services/journalDirectoryBindings'
import type { JournalDirectoryHandle } from '../types/localJournal'
import { createLocalJournalRepository } from '../services/localJournalRepository'
import { createTransferProgress } from '../services/journalTransferProgress'

const state = shallowRef(emptyDirectoryState())
let currentUserId = ''
let channel: BroadcastChannel | undefined
try { if (typeof BroadcastChannel !== 'undefined') channel = new BroadcastChannel('focusnest-journal-bindings') }
catch { /* Browser privacy settings may disable cross-tab notifications. */ }
const controller = createDirectoryController({
  bindings: directoryBindings,
  pick: () => {
    if (directoryCapability(window) !== 'supported') return Promise.reject(new Error('Directory picker unavailable'))
    const browser = window as unknown as { showDirectoryPicker(options: { mode: 'readwrite'; id: string }): Promise<JournalDirectoryHandle> }
    return browser.showDirectoryPicker({ mode: 'readwrite', id: `fn-journal-${currentUserId.replace(/[^a-zA-Z0-9]/g, '').slice(0, 20)}` })
  },
  changed: userId => channel?.postMessage({ userId }),
}, value => { state.value = value })

if (channel) channel.onmessage = event => {
  if (currentUserId && event.data?.userId === currentUserId) void controller.configure(currentUserId, true)
}
export function configureJournalAccount(userId: string) {
  currentUserId = userId
  void controller.configure(userId)
}
export function useJournalStorage() {
  const progress = () => createTransferProgress(controller.connection(), currentUserId)
  return { state: readonly(state), progress, local: (zone: () => string) => createLocalJournalRepository(controller.connection(), zone), choose: controller.choose, checkPermission: () => controller.permission(), authorize: () => controller.permission(true), unbind: controller.unbind, probe: () => controller.probe(), saveProbe: () => controller.probe(true), reloadProbe: controller.reloadProbe, editProbe: controller.editProbe }
}
