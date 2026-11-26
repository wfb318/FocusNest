export interface PresenceEnvironment {
  active: () => boolean
  send: () => Promise<unknown>
  now?: () => number
}

// One controller belongs to one authenticated account layout. It never reads
// routes, journals, filenames or activity contents.
export function createPresenceReporter(environment: PresenceEnvironment) {
  const now = environment.now || Date.now
  let stopped = false, pending = false, lastAttempt: number | undefined

  async function tick() {
    if (stopped || pending || !environment.active()) return
    const time = now()
    if (lastAttempt !== undefined && time >= lastAttempt && time - lastAttempt < 60_000) return
    lastAttempt = time
    pending = true
    try { await environment.send() }
    catch { /* Connectivity/authentication is handled by the normal account flow. */ }
    finally { pending = false }
  }

  function stop() { stopped = true }
  return { tick, stop }
}
