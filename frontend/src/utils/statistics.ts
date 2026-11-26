import { addDays, weekStart } from './scheduleTime'
import type { StatisticsRange } from '../types/statistics'

export function statisticsRange(preset: 'week' | 'month', today: string): StatisticsRange {
  const start = preset === 'week' ? weekStart(today) : today.slice(0, 7) + '-01'
  if (preset === 'week') return { start_date: start, end_date: addDays(start, 6) }
  const nextMonth = new Date(`${start}T12:00:00Z`)
  nextMonth.setUTCMonth(nextMonth.getUTCMonth() + 1)
  return { start_date: start, end_date: addDays(nextMonth.toISOString().slice(0, 10), -1) }
}

export function durationLabel(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(value / 3600), minutes = Math.floor(value / 60) % 60
  return hours ? `${hours} 小时 ${minutes} 分` : minutes ? `${minutes} 分 ${value % 60} 秒` : `${value} 秒`
}
