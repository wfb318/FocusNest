export interface User {
  id: string
  username: string
  email: string
  role: 'user' | 'admin'
  nickname: string | null
  avatar_url: string | null
  timezone: string
  created_at: string
  updated_at: string
}
export interface LoginInput { username: string; password: string }
export interface Registration extends LoginInput { email: string }
export interface TokenResponse { access_token: string; token_type: string; expires_in: number; user: User }
export interface ProfileUpdate { nickname: string | null; avatar_url: string | null; timezone: string }
