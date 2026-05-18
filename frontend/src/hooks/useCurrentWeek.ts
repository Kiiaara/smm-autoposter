import { useCallback } from 'react'
import { format, startOfWeek, addWeeks, subWeeks, parseISO, isValid } from 'date-fns'
import { useSearchParams } from 'react-router-dom'

export function useCurrentWeek() {
  const [searchParams, setSearchParams] = useSearchParams()
  const weekParam = searchParams.get('week')

  // парсим из URL ?week=YYYY-MM-DD или берём текущую неделю
  const fromUrl = weekParam ? parseISO(weekParam) : null
  const weekStart =
    fromUrl && isValid(fromUrl)
      ? startOfWeek(fromUrl, { weekStartsOn: 1 })
      : startOfWeek(new Date(), { weekStartsOn: 1 })

  const weekStartStr = format(weekStart, 'yyyy-MM-dd')

  const setWeek = useCallback(
    (d: Date) => {
      const str = format(startOfWeek(d, { weekStartsOn: 1 }), 'yyyy-MM-dd')
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        next.set('week', str)
        return next
      }, { replace: true })
    },
    [setSearchParams]
  )

  const prevWeek = useCallback(() => setWeek(subWeeks(weekStart, 1)), [weekStart, setWeek])
  const nextWeek = useCallback(() => setWeek(addWeeks(weekStart, 1)), [weekStart, setWeek])
  const goToday = useCallback(() => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('week')
      return next
    }, { replace: true })
  }, [setSearchParams])

  return { weekStart, weekStartStr, prevWeek, nextWeek, goToday }
}
