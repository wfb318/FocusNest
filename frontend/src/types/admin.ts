export interface AdminOverview {
  registered_total: number
  registered_today: number
  registered_week: number
  registered_month: number
  administrators: number
  online_users: number
  timezone: string
  today: string
  server_now: string
  online_window_seconds: number
}

export interface AdminUser {
  id: string
  username: string
  email: string
  nickname: string | null
  role: 'user' | 'admin'
  created_at: string
  last_login_at: string | null
  last_seen_at: string | null
  online: boolean
}

export interface AdminUserQuery {
  page: number
  page_size: number
  search: string
  role?: 'user' | 'admin'
  online?: boolean
}

export interface AdminUserPage {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
  server_now: string
  online_window_seconds: number
}
