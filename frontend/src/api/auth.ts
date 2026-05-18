import client from './client'

export interface AllowedUserRead {
  tg_id: number
  label: string | null
  added_at: string
  is_self: boolean
}

export const getAllowedUsers = () =>
  client.get<AllowedUserRead[]>('/auth/allowed').then(r => r.data)

export const addAllowedUser = (tg_id: number, label?: string) =>
  client.post<AllowedUserRead>('/auth/allowed', { tg_id, label }).then(r => r.data)

export const removeAllowedUser = (tg_id: number) =>
  client.delete(`/auth/allowed/${tg_id}`).then(r => r.data)

export const getMe = () =>
  client.get<{ tg_id: number; username?: string; first_name?: string }>('/auth/me').then(r => r.data)
