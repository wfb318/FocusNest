export type FocusMode = 'pomodoro' | 'countdown' | 'stopwatch' | 'scheduled'
export type FocusAction = 'pause' | 'resume' | 'finish' | 'cancel'
export interface FocusInput {
  mode: FocusMode
  kind: 'focus' | 'break'
  duration_seconds: number | null
  task_id: string | null
  title?: string
  window_start?: string | null
  window_end?: string | null
}
export interface FocusSession extends FocusInput {
  id: string
  status: 'scheduled' | 'running' | 'paused' | 'completed' | 'cancelled'
  occurrence_key: string | null
  elapsed_seconds: number
  started_at: string
  ended_at: string | null
  updated_at: string
  server_now: string
}
export interface FocusPage { items: FocusSession[]; total: number; page: number; page_size: number }
