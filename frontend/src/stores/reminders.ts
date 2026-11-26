import { ref } from 'vue'

interface Preferences { sound: boolean; endSound: boolean; system: boolean }
const preferences = ref<Preferences>({ sound: false, endSound: true, system: false })
const messages = ref<{ id: number; text: string }[]>([])
const audioReady = ref(false)
const storageAvailable = ref(true)
let userId = ''
let audio: AudioContext | undefined
let sequence = 0
const memorySeen = new Set<string>()
function key() { return `focusnest-reminders:${userId}` }
function load() {
  try {
    const value = JSON.parse(localStorage.getItem(key()) || '{}')
    preferences.value = { sound: value.sound === true, endSound: value.endSound !== false, system: value.system === true }
  } catch { preferences.value = { sound: false, endSound: true, system: false }; storageAvailable.value = false }
}
function configure(id: string) {
  userId = id; messages.value = []; memorySeen.clear(); load()
  if (typeof window !== 'undefined') {
    window.removeEventListener('pointerdown', audioGesture, true)
    window.removeEventListener('keydown', audioGesture, true)
    if (id) {
      window.addEventListener('pointerdown', audioGesture, true)
      window.addEventListener('keydown', audioGesture, true)
    }
  }
}
function save() { try { localStorage.setItem(key(), JSON.stringify(preferences.value)) } catch { storageAvailable.value = false } }
function beep(ending = false): boolean {
  audioReady.value = audio?.state === 'running'
  if (!audio || !audioReady.value) return false
  try {
    const tones = ending ? [660, 830, 990] : [660]
    tones.forEach((frequency, index) => {
      const context = audio!, oscillator = context.createOscillator(), gain = context.createGain()
      const start = context.currentTime + index * .45, length = ending ? .6 : .4
      oscillator.connect(gain); gain.connect(context.destination)
      oscillator.frequency.value = frequency
      gain.gain.setValueAtTime(.001, start)
      gain.gain.exponentialRampToValueAtTime(ending ? .14 : .08, start + .025)
      gain.gain.exponentialRampToValueAtTime(.001, start + length)
      oscillator.onended = () => { oscillator.disconnect(); gain.disconnect() }
      oscillator.start(start); oscillator.stop(start + length)
    })
    return true
  } catch { audioReady.value = false; return false }
}
async function prepareAudio() {
  try {
    if (!audio || audio.state === 'closed') {
      audio = new AudioContext()
      audio.onstatechange = () => { audioReady.value = audio?.state === 'running' }
    }
    if (audio.state !== 'running') await audio.resume()
    audioReady.value = audio.state === 'running'
  } catch { audioReady.value = false }
}
function audioGesture(event: Event) {
  if (event.isTrusted && userId && (preferences.value.sound || preferences.value.endSound) && audio?.state !== 'running') void prepareAudio()
}
async function enableSound() {
  await prepareAudio(); preferences.value.sound = audioReady.value; save(); beep()
}
async function testEndSound() {
  preferences.value.endSound = true; save(); await prepareAudio(); beep(true)
}
async function enableSystem() {
  if (!('Notification' in window)) return
  const result = await Notification.requestPermission()
  preferences.value.system = result === 'granted'; save()
}
function push(text: string) { messages.value = [...messages.value.slice(-3), { id: ++sequence, text }] }
async function notify(id: string, text: string) {
  const owner = userId
  if (!owner) return
  const run = () => {
    if (owner !== userId) return
    const ledgerKey = `${key()}:seen`
    let seen: Record<string, number> = {}
    try {
      const parsed = JSON.parse(localStorage.getItem(ledgerKey) || '{}')
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) seen = parsed
    } catch { storageAvailable.value = false }
    if (!seen[id] && !memorySeen.has(id)) {
      memorySeen.add(id); seen[id] = Date.now()
      push(text)
      if (preferences.value.system && 'Notification' in window && Notification.permission === 'granted') {
        try { new Notification('FocusNest', { body: text, tag: id }) } catch { /* Site notification remains available. */ }
      }
    }
    // A tab without audio permission must not consume another tab's sound event.
    const soundId = `audio:${id}`
    const ending = id.endsWith(':end')
    if (!seen[soundId] && !memorySeen.has(soundId) && (ending ? preferences.value.endSound : preferences.value.sound) && beep(ending)) {
      seen[soundId] = Date.now(); memorySeen.add(soundId)
    }
    seen = Object.fromEntries(Object.entries(seen).filter(([, at]) => at > Date.now() - 7 * 86400000).slice(-1000))
    try { localStorage.setItem(ledgerKey, JSON.stringify(seen)) } catch { storageAvailable.value = false }
  }
  if (navigator.locks) await navigator.locks.request(`focusnest-alert:${owner}`, run)
  else run()
}
export function useReminders() {
  return { preferences, messages, audioReady, storageAvailable, configure, save, enableSound, testEndSound, enableSystem, notify, push, dismiss: (id: number) => { messages.value = messages.value.filter(item => item.id !== id) } }
}
