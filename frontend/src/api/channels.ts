import client from './client'
import type { Channel, ChannelCreate } from '../types'

export const getChannels = (platform?: string) =>
  client.get<Channel[]>('/channels', { params: platform ? { platform } : {} }).then(r => r.data)

export const createChannel = (data: ChannelCreate) =>
  client.post<Channel>('/channels', data).then(r => r.data)

export const updateChannel = (id: number, data: Partial<ChannelCreate> & { is_active?: boolean }) =>
  client.patch<Channel>(`/channels/${id}`, data).then(r => r.data)

export const deleteChannel = (id: number) =>
  client.delete(`/channels/${id}`).then(r => r.data)

export const testChannel = (id: number) =>
  client.post<{ ok: boolean; message: string }>(`/channels/${id}/test`).then(r => r.data)
