import client from './client'
import type { CalendarResponse } from '../types'

export const getCalendar = (week_start: string) =>
  client.get<CalendarResponse>('/calendar', { params: { week_start } }).then(r => r.data)
