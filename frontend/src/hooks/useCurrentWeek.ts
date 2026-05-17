import { useState, useCallback } from 'react'
import { format, startOfWeek, addWeeks, subWeeks } from 'date-fns'

export function useCurrentWeek() {
  const [weekStart, setWeekStart] = useState<Date>(() =>
    startOfWeek(new Date(), { weekStartsOn: 1 })
  )

  const weekStartStr = format(weekStart, 'yyyy-MM-dd')

  const prevWeek = useCallback(() => setWeekStart(d => subWeeks(d, 1)), [])
  const nextWeek = useCallback(() => setWeekStart(d => addWeeks(d, 1)), [])
  const goToday = useCallback(() => setWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 })), [])

  return { weekStart, weekStartStr, prevWeek, nextWeek, goToday }
}
