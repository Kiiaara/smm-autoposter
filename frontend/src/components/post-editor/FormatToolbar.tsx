import styles from './FormatToolbar.module.css'

type FormatType = 'bold' | 'italic' | 'underline' | 'strike' | 'code' | 'spoiler' | 'link'

interface Props {
  onFormat: (type: FormatType, url?: string) => void
  onEmoji: () => void
}

const BUTTONS: { type: FormatType; label: string; title: string; style?: React.CSSProperties }[] = [
  { type: 'bold', label: 'B', title: 'Жирный (выдели → жми ещё раз чтобы снять)', style: { fontWeight: 700 } },
  { type: 'italic', label: 'I', title: 'Курсив', style: { fontStyle: 'italic' } },
  { type: 'underline', label: 'U', title: 'Подчёркнутый', style: { textDecoration: 'underline' } },
  { type: 'strike', label: 'S', title: 'Зачёркнутый', style: { textDecoration: 'line-through' } },
  { type: 'code', label: '</>', title: 'Моноширинный код', style: { fontFamily: 'monospace' } },
  { type: 'spoiler', label: '||', title: 'Спойлер' },
  { type: 'link', label: '🔗', title: 'Вставить ссылку' },
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
          onMouseDown={e => e.preventDefault()}
          onClick={() => b.type === 'link' ? handleLink() : onFormat(b.type)}
          style={b.style}
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
