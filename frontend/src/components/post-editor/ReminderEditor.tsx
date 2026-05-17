import { useEditorStore } from '../../store/editorStore'
import styles from './ReminderEditor.module.css'

export default function ReminderEditor() {
  const { reminders, addReminder, removeReminder } = useEditorStore()

  function addAuto() {
    addReminder({
      message: 'Пост вышел, не забудь обновить ссылку в вечернем посте',
      send_at: null,
    })
  }

  function addCustom() {
    addReminder({
      message: 'Не забудь обновить ссылку в посте!',
      send_at: '',
    })
  }

  function update(idx: number, field: 'message' | 'send_at', val: string) {
    useEditorStore.setState(s => {
      const arr = [...s.reminders]
      arr[idx] = { ...arr[idx], [field]: val }
      return { reminders: arr }
    })
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span className={styles.title}>Напоминания в TG</span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={addAuto}>
            + После публикации
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={addCustom}>
            + На время
          </button>
        </div>
      </div>
      {reminders.length === 0 && (
        <p className={styles.empty}>Нет напоминаний - добавь, если нужно подправить ссылку</p>
      )}
      {reminders.map((r, i) => {
        const isAuto = r.send_at === null
        return (
          <div key={i} className={styles.row}>
            {isAuto ? (
              <span
                className="btn btn-secondary btn-sm"
                style={{ flex: '0 0 180px', cursor: 'default', pointerEvents: 'none' }}
                title="Через 2 мин после публикации поста"
              >
                После публикации
              </span>
            ) : (
              <input
                type="datetime-local"
                className="input"
                value={r.send_at ?? ''}
                onChange={e => update(i, 'send_at', e.target.value)}
                style={{ flex: '0 0 180px' }}
              />
            )}
            <input
              className="input"
              value={r.message}
              onChange={e => update(i, 'message', e.target.value)}
              placeholder="Текст напоминания..."
              style={{ flex: 1 }}
            />
            <button type="button" className="btn btn-icon" onClick={() => removeReminder(i)}>x</button>
          </div>
        )
      })}
    </div>
  )
}
