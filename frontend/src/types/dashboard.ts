import type { Task } from './task'
export interface Dashboard {
  today: string; timezone: string; server_now: string
  task_total: number; task_done: number; overdue_tasks: number
  tasks: Pick<Task, 'id' | 'title' | 'status' | 'priority' | 'scheduled_date' | 'due_date'>[]
  focus_seconds: number; focus_completed: number
  active_focus_id: string | null; active_focus_seconds: number
  journal_source: 'local'; journal_written: boolean | null; journal_title: string | null
  recent_notes: { id: string; title: string; pinned: boolean; updated_at: string; storage_mode: 'cloud' | 'cloud_encrypted' }[]
  recent_documents: { id: string; title: string; kind: string; updated_at: string }[]
}
