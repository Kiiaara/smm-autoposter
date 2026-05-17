import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { format, addDays } from 'date-fns'
import { ru } from 'date-fns/locale'
import { getCalendar } from '../api/calendar'
import { useCurrentWeek } from '../hooks/useCurrentWeek'
import WeekCalendar from '../components/calendar/WeekCalendar'
import styles from './CalendarPage.module.css'

export default function CalendarPage() {
  const navigate = useNavigate()
  const { weekStart, weekStartStr, prevWeek, nextWeek, goToday } = useCurrentWeek()

  const { data, isLoading } = useQuery({
    queryKey: ['calendar', weekStartStr],
    queryFn: () => getCalendar(weekStartStr),
  })

  const weekEnd = addDays(weekStart, 6)
  const weekLabel = `${format(weekStart, 'd MMM', { locale: ru })} - ${format(weekEnd, 'd MMM yyyy', { locale: ru })}`

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <button className={styles.navBtn} onClick={prevWeek} title="Предыдущая неделя">&#8249;</button>
        <span className={styles.weekLabel}>{weekLabel}</span>
        <button className={styles.navBtn} onClick={nextWeek} title="Следующая неделя">&#8250;</button>
        <button className={styles.todayBtn} onClick={goToday}>Сегодня</button>
      </div>

      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : (
        <WeekCalendar
          weekStart={weekStart}
          days={data?.days ?? []}
          onPostClick={id => navigate(`/posts/${id}/edit`)}
          onSlotClick={(date, time) => navigate(`/posts/new?date=${date}&time=${time}`)}
        />
      )}
    </div>
  )
}
