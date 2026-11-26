import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { FocusSession } from '../types/focus'
import type { ScheduleChange, ScheduleCreate, ScheduleTemplate, ScheduleTemplateReview, ScheduleWeek } from '../types/schedule'

export async function listSchedule(start: string, end: string): Promise<ScheduleWeek> {
  return (await apiClient.get<ApiResponse<ScheduleWeek>>('/schedules', { params: { start_date: start, end_date: end } })).data.data!
}
export async function createSchedule(value: ScheduleCreate) { await apiClient.post('/schedules', value) }
export async function editSchedule(id: string, value: ScheduleChange) { await apiClient.put(`/schedules/${id}`, value) }
export async function removeSchedule(id: string, value: Pick<ScheduleChange, 'scope' | 'occurrence_date' | 'revision'>) { await apiClient.post(`/schedules/${id}/remove`, value) }
export async function startOccurrence(id: string, date: string): Promise<FocusSession> {
  return (await apiClient.post<ApiResponse<FocusSession>>(`/schedules/${id}/start`, null, { params: { occurrence_date: date } })).data.data!
}

export async function listScheduleTemplates() {
  return (await apiClient.get<ApiResponse<ScheduleTemplate[]>>('/schedules/templates')).data.data!
}
export async function saveScheduleTemplate(week_start: string, name: string) {
  return (await apiClient.post<ApiResponse<ScheduleTemplate>>('/schedules/templates', { week_start, name })).data.data!
}
export async function applyScheduleTemplate(id: string, week_start: string, expected_template_id: string | null) {
  await apiClient.post(`/schedules/templates/${id}/apply`, { week_start, expected_template_id })
}
export async function getScheduleTemplateReview() {
  return (await apiClient.get<ApiResponse<ScheduleTemplateReview>>('/schedules/template-review')).data.data
}
export async function keepScheduleWeek(week: string) {
  await apiClient.post(`/schedules/template-review/${week}/keep`)
}
export async function carryScheduleTemplate() {
  await apiClient.post('/schedules/templates/carry')
}
