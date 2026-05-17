import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { getSlots, createSlot, deleteSlot } from '../../api/scheduleSlots'
import styles from './SlotSettings.module.css'

const DAYS = [
  { idx: 0, short: 'Пн', full: 'Понедельник' },
  { idx: 1, short: 'Вт', full: 'Вторник' },
  { idx: 2, short: 'Ср', full: 'Среда' },
  { idx: 3, short: 'Чт', full: 'Четверг' },
  { idx: 4, short: 'Пт', full: 'Пятница' },
  { idx: 5, short: 'Сб', full: 'Суббота' },
  { idx: 6, short: 'Вс', full: 'Воскресенье' },
]

export default function SlotSettings() {
  const qc = useQueryClient()
  const [newTime, setNewTime] = useState('')
  const [selectedDays, setSelectedDays] = useState<number[]>([])
  const [adding, setAdding] = useState(false)

  const { data: slots = [] } = useQuery({ queryKey: ['slots'], queryFn: () => getSlots() })

  const createMutation = useMutation({
    mutationFn: ({ day, time }: { day: number; time: string }) => createSlot(day, time),
    onError: (e: any) => {
      // ignore 409 (already exists) - we silently skip duplicates
      if (e?.response?.status !== 409) {
        toast.error(e?.response?.data?.detail ?? 'Ошибка')
      }
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSlot,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['slots'] }),
  })

  // group slots by time - each unique time aggregates a set of days
  const groupedByTime = useMemo(() => {
    const map = new Map<string, { id: number; day: number }[]>()
    for (const s of slots) {
      if (!map.has(s.slot_time)) map.set(s.slot_time, [])
      map.get(s.slot_time)!.push({ id: s.id, day: s.day_of_week })
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, entries]) => ({ time, entries: entries.sort((a, b) => a.day - b.day) }))
  }, [slots])

  function toggleDay(d: number) {
    setSelectedDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d].sort())
  }

  function selectAll() { setSelectedDays([0, 1, 2, 3, 4, 5, 6]) }
  function selectWeekdays() { setSelectedDays([0, 1, 2, 3, 4]) }
  function selectWeekend() { setSelectedDays([5, 6]) }
  function clearDays() { setSelectedDays([]) }

  async function handleAdd() {
    if (!newTime || selectedDays.length === 0) return
    // create slots in parallel
    await Promise.all(selectedDays.map(day => createMutation.mutateAsync({ day, time: newTime })))
    qc.invalidateQueries({ queryKey: ['slots'] })
    toast.success(`Добавлено: ${newTime} на ${selectedDays.length} ${selectedDays.length === 1 ? 'день' : 'дней'}`)
    setNewTime('')
    setSelectedDays([])
    setAdding(false)
  }

  async function deleteTimeGroup(time: string) {
    const group = groupedByTime.find(g => g.time === time)
    if (!group) return
    await Promise.all(group.entries.map(e => deleteMutation.mutateAsync(e.id)))
    toast.success(`Удалено: ${time}`)
  }

  async function toggleDayInGroup(time: string, day: number) {
    const group = groupedByTime.find(g => g.time === time)
    if (!group) return
    const existing = group.entries.find(e => e.day === day)
    if (existing) {
      await deleteMutation.mutateAsync(existing.id)
    } else {
      await createMutation.mutateAsync({ day, time })
      qc.invalidateQueries({ queryKey: ['slots'] })
    }
  }

  return (
    <div className={styles.wrapper}>
      <h3 className={styles.title}>Расписание</h3>
      <p className={styles.hint}>
        Настрой время публикаций и дни недели для каждого слота. Эти слоты будут предлагаться при создании поста.
      </p>

      {/* Add new slot form */}
      {!adding ? (
        <button className="btn btn-primary" onClick={() => setAdding(true)} style={{ alignSelf: 'flex-start' }}>
          + Добавить слот
        </button>
      ) : (
        <div className={styles.addCard}>
          <div className={styles.addStep}>
            <label className={styles.stepLabel}>1. Время</label>
            <input
              type="time"
              className="input"
              value={newTime}
              onChange={e => setNewTime(e.target.value)}
              style={{ maxWidth: 160 }}
            />
          </div>

          <div className={styles.addStep}>
            <label className={styles.stepLabel}>2. Дни недели</label>
            <div className={styles.quickButtons}>
              <button type="button" className={styles.quickBtn} onClick={selectAll}>Все дни</button>
              <button type="button" className={styles.quickBtn} onClick={selectWeekdays}>Будни</button>
              <button type="button" className={styles.quickBtn} onClick={selectWeekend}>Выходные</button>
              {selectedDays.length > 0 && (
                <button type="button" className={styles.quickBtn} onClick={clearDays}>Сбросить</button>
              )}
            </div>
            <div className={styles.daysRow}>
              {DAYS.map(d => (
                <button
                  key={d.idx}
                  type="button"
                  className={`${styles.dayBtn} ${selectedDays.includes(d.idx) ? styles.dayActive : ''}`}
                  onClick={() => toggleDay(d.idx)}
                >
                  {d.short}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.addActions}>
            <button
              className="btn btn-primary"
              onClick={handleAdd}
              disabled={!newTime || selectedDays.length === 0}
            >
              Добавить
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => { setAdding(false); setNewTime(''); setSelectedDays([]) }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* Existing slots */}
      {groupedByTime.length === 0 && !adding && (
        <p className={styles.empty}>Слотов ещё нет - добавь первый</p>
      )}

      <div className={styles.slotsList}>
        {groupedByTime.map(({ time, entries }) => {
          const activeDays = new Set(entries.map(e => e.day))
          return (
            <div key={time} className={styles.slotCard}>
              <div className={styles.slotTime}>{time}</div>
              <div className={styles.daysRow}>
                {DAYS.map(d => (
                  <button
                    key={d.idx}
                    type="button"
                    className={`${styles.dayBtn} ${activeDays.has(d.idx) ? styles.dayActive : ''}`}
                    onClick={() => toggleDayInGroup(time, d.idx)}
                    title={d.full}
                  >
                    {d.short}
                  </button>
                ))}
              </div>
              <button className="btn btn-danger btn-sm" onClick={() => deleteTimeGroup(time)}>
                Удалить
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
