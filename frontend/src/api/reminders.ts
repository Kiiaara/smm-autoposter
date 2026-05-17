import client from './client'
import type { Reminder } from '../types'

export const getReminders = (post_id?: number) =>
  client.get<Reminder[]>('/reminders', { params: post_id != null ? { post_id } : {} }).then(r => r.data)

export const createReminder = (data: { post_id: number; message: string; send_at: string | null }) =>
  client.post<Reminder>('/reminders', data).then(r => r.data)

export const deleteReminder = (id: number) =>
  client.delete(`/reminders/${id}`).then(r => r.data)
