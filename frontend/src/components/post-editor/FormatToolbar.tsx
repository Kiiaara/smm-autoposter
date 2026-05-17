import styles from './FormatToolbar.module.css'

type FormatType = 'bold' | 'italic' | 'strike' | 'code' | 'spoiler' | 'link'

interface Props {
  onFormat: (type: FormatType, url?: string) => void
  onEmoji: () => void
}

const BUTTONS: { type: FormatType; label: string; title: string }[] = [
  { type: 'bold', label: 'B', title: 'Жирный' },
  { type: 'italic', label: 'I', title: 'Курсив' },
  { type: 'strike', label: 'S', title: 'Зачёркнутый' },
  { type: 'code', label: '<>', title: 'Код' },
  { type: 'spoiler', label: '||', title: 'Спойлер' },
  { type: 'link', label: 'Ссылка', title: 'Вставить ссылку' },
]

export default function FormatToolbar({ onFormat, onEmoji }: Props) {
  function handleLink() {
    const url = prompt('URL ссылки:')
    if (url) onFormat('link', url)
  }

  return (
    <div className={styles.toolbar}>
      {BUTTONS.map(b => (
        <button
          key={b.type}
          type="button"
          className={styles.btn}
          title={b.title}
          onClick={() => b.type === 'link' ? handleLink() : onFormat(b.type)}
          style={b.type === 'bold' ? { fontWeight: 700 } : b.type === 'italic' ? { fontStyle: 'italic' } : {}}
        >
          {b.label}
        </button>
      ))}
      <button type="button" className={styles.btn} title="Эмодзи" onClick={onEmoji}>
        😊
      </button>
    </div>
  )
}
