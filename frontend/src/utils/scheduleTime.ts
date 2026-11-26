export function dateInZone(instant: number, zone: string): string {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(instant)
  const get = (key: string) => p.find(item => item.type === key)!.value
  return `${get('year')}-${get('month')}-${get('day')}`
}
export function addDays(date: string, amount: number): string {
  const value = new Date(`${date}T12:00:00Z`); value.setUTCDate(value.getUTCDate() + amount)
  return value.toISOString().slice(0, 10)
}
export function weekStart(date: string): string {
  const weekday = new Date(`${date}T12:00:00Z`).getUTCDay()
  return addDays(date, -(weekday + 6) % 7)
}
export function minuteLabel(minute: number): string { return `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}` }
export function secondsLabel(value: number): string {
  const n = Math.max(0, Math.ceil(value))
  return [Math.floor(n / 3600), Math.floor(n / 60) % 60, n % 60].map(v => String(v).padStart(2, '0')).join(':')
}
// datetime-local has no timezone. Interpret it explicitly in the user's profile zone.
export function zonedInstant(local: string, zone: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local)) throw new Error('请选择有效的开始和结束时间。')
  const formatter = new Intl.DateTimeFormat('sv-SE', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
  const wall = (stamp: number) => formatter.format(stamp).replace(' ', 'T')
  const target = Date.parse(`${local}:00Z`)
  const candidates = [-86400000, 0, 86400000].map(delta => {
    const sample = target + delta
    const offset = Date.parse(`${wall(sample)}Z`) - sample
    return target - offset
  }).filter(stamp => wall(stamp) === `${local}:00`).sort((a, b) => a - b)
  if (!candidates.length) throw new Error('该时区不存在这个时间（可能处于夏令时跳转），请选择其他时间。')
  return new Date(candidates[0]!).toISOString()
}
