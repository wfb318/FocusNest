export interface ScheduleFields {
  title: string; notes: string; start_minute: number; end_minute: number
  task_id: string | null; timer_enabled: boolean; remind_start: boolean; remind_end: boolean
}
export interface ScheduleCreate extends ScheduleFields { weekday: number; effective_from: string; timezone: string; repeat_weekly: boolean }
export interface ScheduleChange extends ScheduleFields { scope: 'single' | 'future'; occurrence_date: string; revision: number; weekday: number }
export interface Occurrence extends ScheduleFields {
  schedule_id: string; key: string; occurrence_date: string; weekday: number; timezone: string
  starts_at: string | null; ends_at: string | null; skipped: boolean; time_warning: boolean
  overridden: boolean; revision: number; repeats: boolean
}
export interface ScheduleWeek { items: Occurrence[]; server_now: string; template_id: string | null }
export interface ScheduleTemplate { id: string; name: string; entry_count: number }
export interface ScheduleTemplateReview {
  week_start: string
  current_template_id: string | null
  planned_template_id: string | null
}
