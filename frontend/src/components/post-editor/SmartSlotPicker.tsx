import { useQuery } from '@tanstack/react-query'
import { getAvailableSlots } from '../../api/scheduleSlots'
import { useEditorStore } from '../../store/editorStore'
import styles from './SmartSlotPicker.module.css'

interface Props {
  date: string  // YYYY-MM-DD
}

export default function SmartSlotPicker({ date }: Props) {
  const { setScheduledAt, scheduledAt } = useEditorStore()

  const { data: slots = [] } = useQuery({
    queryKey: ['slots-available', date],
    queryFn: () => getAvailableSlots(date),
    enabled: !!date,
  })

  if (slots.length === 0) return null

  function selectSlot(time: string) {
    setScheduledAt(`${date}T${time}`)
  }

  const selectedTime = scheduledAt?.startsWith(date) ? scheduledAt.slice(11, 16) : null

  return (
    <div className={styles.wrapper}>
      <span className={styles.label}>Слоты расписания:</span>
      <div className={styles.slots}>
        {slots.map(s => (
          <button
            key={s.slot_time}
            type="button"
            disabled={!s.is_free}
            className={`${styles.slot} ${!s.is_free ? styles.busy : ''} ${selectedTime === s.slot_time ? styles.selected : ''}`}
            onClick={() => s.is_free && selectSlot(s.slot_time)}
          >
            {s.slot_time}
          </button>
        ))}
      </div>
    </div>
  )
}
