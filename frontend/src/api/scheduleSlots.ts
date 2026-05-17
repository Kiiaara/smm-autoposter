import client from './client'
import type { ScheduleSlot, AvailableSlot } from '../types'

export const getSlots = (day_of_week?: number) =>
  client.get<ScheduleSlot[]>('/schedule-slots', { params: day_of_week != null ? { day_of_week } : {} }).then(r => r.data)

export const createSlot = (day_of_week: number, slot_time: string) =>
  client.post<ScheduleSlot>('/schedule-slots', { day_of_week, slot_time }).then(r => r.data)

export const deleteSlot = (id: number) =>
  client.delete(`/schedule-slots/${id}`).then(r => r.data)

export const getAvailableSlots = (date: string) =>
  client.get<AvailableSlot[]>('/schedule-slots/available', { params: { date_str: date } }).then(r => r.data)
