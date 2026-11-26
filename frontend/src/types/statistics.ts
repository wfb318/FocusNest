export interface StatisticsRange { start_date: string; end_date: string }
export interface FocusSummary { seconds: number; completed: number; active: number }
export interface DailyFocus extends FocusSummary { date: string }
export type FocusMode = 'pomodoro' | 'countdown' | 'stopwatch' | 'scheduled'
export interface Statistics extends StatisticsRange {
  timezone: string
  today: string
  server_now: string
  focus: FocusSummary
  tasks: {
    total: number
    todo: number
    doing: number
    done: number
    overdue: number
    completion_rate: number | null
  }
  daily: DailyFocus[]
  modes: (FocusSummary & { mode: FocusMode })[]
}
