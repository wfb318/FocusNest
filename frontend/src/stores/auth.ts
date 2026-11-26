import { ref } from 'vue'
import { defineStore } from 'pinia'
import { configureAuthTransport } from '../api/client'
import { getAccount, loginAccount, logoutAccount, refreshAccount, updateAccount } from '../api/auth'
import type { LoginInput, ProfileUpdate, TokenResponse, User } from '../types/auth'
import { configureJournalAccount } from './journalStorage'

const sessionMarkerKey = 'focusnest-session-change'

function readSessionMarker() {
  try { return window.localStorage.getItem(sessionMarkerKey) }
  catch { return null }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref('')
  const initialized = ref(false)
  let pendingRefresh: Promise<boolean> | null = null
  let generation = 0
  let marker = readSessionMarker()
  let channel: BroadcastChannel | undefined
  try { channel = new BroadcastChannel(sessionMarkerKey) }
  catch { /* The storage event can still notify other tabs. */ }

  function clear() {
    generation++
    configureJournalAccount('')
    accessToken.value = ''
    user.value = null
  }
  function invalidate() {
    initialized.value = true
    clear()
  }
  function sessionVersion() {
    const shared = readSessionMarker()
    if (shared !== null && shared !== marker) {
      marker = shared
      invalidate()
    }
    return generation
  }
  function publishSessionChange() {
    const next = crypto.getRandomValues(new Uint32Array(4)).join('-')
    let persisted = false
    try {
      window.localStorage.setItem(sessionMarkerKey, next)
      marker = next
      persisted = true
    }
    catch { /* Use the channel when browser storage is unavailable. */ }
    channel?.postMessage({ persisted })
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key === sessionMarkerKey) sessionVersion()
  }
  window.addEventListener('storage', onStorage)
  if (channel) channel.onmessage = event => {
    if (event.data?.persisted === true) sessionVersion()
    else if (event.data?.persisted === false) invalidate()
  }

  function accept(result: TokenResponse) {
    configureJournalAccount(result.user.id)
    accessToken.value = result.access_token
    user.value = result.user
  }
  // Login, refresh and logout all mutate the browser's shared refresh cookie.
  const withCookieLock = <T>(run: () => Promise<T>) =>
    navigator.locks ? navigator.locks.request('focusnest-refresh', run) : run()

  function refresh(): Promise<boolean> {
    if (pendingRefresh) return pendingRefresh
    const version = sessionVersion()
    const owner = user.value?.id
    const run = async () => {
      if (sessionVersion() !== version) return false
      try {
        const result = await refreshAccount()
        if (sessionVersion() !== version) return false
        if (owner && result.user.id !== owner) { invalidate(); return false }
        accept(result)
        return true
      } catch {
        if (sessionVersion() === version) clear()
        return false
      }
    }
    pendingRefresh = withCookieLock(run).finally(() => { pendingRefresh = null })
    return pendingRefresh
  }
  async function initialize() {
    if (initialized.value) return
    await refresh()
    initialized.value = true
  }
  async function login(input: LoginInput) {
    await withCookieLock(async () => {
      const version = sessionVersion()
      const result = await loginAccount(input)
      if (sessionVersion() !== version) throw new Error('Session changed')
      clear()
      publishSessionChange()
      accept(result)
      initialized.value = true
    })
  }
  async function logout() {
    const version = sessionVersion()
    await withCookieLock(async () => {
      if (sessionVersion() !== version || !user.value) return
      await logoutAccount()
      if (sessionVersion() !== version) return
      invalidate()
      publishSessionChange()
    })
  }
  async function saveProfile(input: ProfileUpdate) {
    const version = sessionVersion()
    const result = await updateAccount(input)
    if (sessionVersion() === version && result.id === user.value?.id) user.value = result
  }
  async function reloadProfile() {
    const version = sessionVersion(), owner = user.value?.id
    if (!owner) return
    const result = await getAccount()
    if (sessionVersion() === version && result.id === owner) user.value = result
  }
  configureAuthTransport(() => accessToken.value, refresh, sessionVersion)
  return { user, initialized, initialize, login, logout, saveProfile, reloadProfile }
})
