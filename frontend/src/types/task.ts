export type TaskStatus = 'todo' | 'doing' | 'done'
export type TaskPriority = 'low' | 'medium' | 'high'

export interface TaskInput {
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  scheduled_date: string | null
  due_date: string | null
  estimated_minutes: number | null
}

export interface Task extends TaskInput {
  id: string
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskPage { items: Task[]; total: number; page: number; page_size: number }
export interface TaskQuery {
  page: number
  page_size: number
  today?: boolean
  status?: TaskStatus
  priority?: TaskPriority
  scheduled_date?: string
  due_date?: string
}
