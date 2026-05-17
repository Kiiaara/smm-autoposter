import { useState, useRef, useEffect } from 'react'
import { format, addMonths, subMonths, startOfMonth, startOfWeek, addDays, isSameMonth, isToday, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useQuery } from '@tanstack/react-query'
import { getAvailableSlots } from '../../api/scheduleSlots'
import { useEditorStore } from '../../store/editorStore'
import styles from './DateTimePicker.module.css'

function generateTimeSlots(): string[] {
  // каждые 15 минут как быстрые слоты
  const slots: string[] = []
  for (let h = 0; h < 24; h++) {
    for (const m of [0, 15, 30, 45]) {
      slots.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
    }
  }
  return slots
}

const TIME_SLOTS = generateTimeSlots()

export default function DateTimePicker() {
  const { scheduledAt, setScheduledAt } = useEditorStore()
  const [open, setOpen] = useState(false)
  const [viewMonth, setViewMonth] = useState(new Date())
  const ref = useRef<HTMLDivElement>(null)

  const selectedDate = scheduledAt ? scheduledAt.slice(0, 10) : ''
  const selectedTime = scheduledAt ? scheduledAt.slice(11, 16) : ''

  // close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const { data: smartSlots = [] } = useQuery({
    queryKey: ['slots-available', selectedDate],
    queryFn: () => getAvailableSlots(selectedDate),
    enabled: !!selectedDate,
  })

  const smartSlotTimes = new Set(smartSlots.filter(s => s.is_free).map(s => s.slot_time))
  const busySlotTimes = new Set(smartSlots.filter(s => !s.is_free).map(s => s.slot_time))

  function selectDate(d: Date) {
    const dateStr = format(d, 'yyyy-MM-dd')
    // если время уже было - подставляем, иначе ставим 12:00 как дефолт
    const time = selectedTime || '12:00'
    setScheduledAt(`${dateStr}T${time}`)
  }

  function selectTime(t: string) {
    // если даты нет - подставляем сегодня
    const date = selectedDate || format(new Date(), 'yyyy-MM-dd')
    setScheduledAt(`${date}T${t}`)
    setOpen(false)
  }

  function clear() {
    setScheduledAt('')
    setOpen(false)
  }

  // build calendar grid
  const monthStart = startOfMonth(viewMonth)
  const gridStart = startOfWeek(monthStart, { weekStartsOn: 1 })
  const days: Date[] = []
  for (let i = 0; i < 42; i++) days.push(addDays(gridStart, i))

  let displayValue = 'Выбрать дату и время'
  if (selectedDate) {
    try {
      const parsed = parseISO(selectedDate)
      const dateLabel = format(parsed, 'd MMM yyyy', { locale: ru })
      displayValue = selectedTime
        ? `${dateLabel}, ${selectedTime}`
        : `${dateLabel}, выбери время`
    } catch {
      displayValue = 'Выбрать дату и время'
    }
  }

  return (
    <div className={styles.wrapper} ref={ref}>
      <label className={styles.label}>Дата и время публикации</label>

      <button type="button" className={styles.trigger} onClick={() => setOpen(v => !v)}>
        <span className={scheduledAt ? styles.triggerValue : styles.triggerPlaceholder}>
          {displayValue}
        </span>
        <span className={styles.triggerIcon}>📅</span>
      </button>

      {selectedTime === '12:00' && (
        <div className={styles.noonHint}>
          🔔 После публикации придёт уведомление в TG со ссылкой на пост
        </div>
      )}

      {scheduledAt && (
        <button type="button" className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={clear}>
          Очистить (сохранить как черновик)
        </button>
      )}

      {open && (
        <div className={styles.popup}>
          <div className={styles.popupInner}>
            {/* Calendar */}
            <div className={styles.calendar}>
              <div className={styles.calHeader}>
                <button type="button" className={styles.navBtn} onClick={() => setViewMonth(m => subMonths(m, 1))}>&#8249;</button>
                <span className={styles.monthLabel}>{format(viewMonth, 'LLLL yyyy', { locale: ru })}</span>
                <button type="button" className={styles.navBtn} onClick={() => setViewMonth(m => addMonths(m, 1))}>&#8250;</button>
              </div>
              <div className={styles.weekdays}>
                {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(d => <span key={d}>{d}</span>)}
              </div>
              <div className={styles.grid}>
                {days.map((d, i) => {
                  const dateStr = format(d, 'yyyy-MM-dd')
                  const isSelected = selectedDate === dateStr
                  const isCurrentMonth = isSameMonth(d, viewMonth)
                  const isPast = d < new Date(new Date().setHours(0,0,0,0))
                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={isPast}
                      className={`${styles.day}
                        ${isSelected ? styles.daySelected : ''}
                        ${isToday(d) ? styles.dayToday : ''}
                        ${!isCurrentMonth ? styles.dayOtherMonth : ''}
                        ${isPast ? styles.dayPast : ''}
                      `}
                      onClick={() => selectDate(d)}
                    >
                      {format(d, 'd')}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Time slots */}
            <div className={styles.timeSide}>
              <div className={styles.timeHeader}>Время</div>
              <input
                type="time"
                step={60}
                className={styles.timeInput}
                value={selectedTime}
                onChange={e => {
                  const v = e.target.value
                  // принимаем только полностью валидное HH:MM
                  if (!/^\d{2}:\d{2}$/.test(v)) return
                  const date = selectedDate || format(new Date(), 'yyyy-MM-dd')
                  setScheduledAt(`${date}T${v}`)
                }}
                onClick={e => e.stopPropagation()}
                title="Любое время с точностью до минуты"
              />
              <div className={styles.timeSubHeader}>Быстро</div>
              <div className={styles.timeList}>
                {TIME_SLOTS.map(t => {
                  const isSmart = smartSlotTimes.has(t)
                  const isBusy = busySlotTimes.has(t)
                  const isSelected = selectedTime === t
                  return (
                    <button
                      key={t}
                      type="button"
                      className={`${styles.timeSlot}
                        ${isSelected ? styles.timeSelected : ''}
                        ${isSmart ? styles.timeSmart : ''}
                        ${isBusy ? styles.timeBusy : ''}
                      `}
                      onClick={() => selectTime(t)}
                      title={isSmart ? 'Слот расписания' : isBusy ? 'Занято' : ''}
                    >
                      {t}
                      {isSmart && <span className={styles.smartDot} />}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
