import { useState } from 'react'
import { useEditorStore } from '../../store/editorStore'
import RichTextEditor from './RichTextEditor'
import PlainTextEditor from './PlainTextEditor'
import styles from './DualTextEditor.module.css'

type Tab = 'tg' | 'plain'

export default function DualTextEditor() {
  const { selectedNetworks } = useEditorStore()
  const [tab, setTab] = useState<Tab>('tg')

  const hasTg = selectedNetworks.includes('tg')
  const hasPlain = selectedNetworks.some(n => n !== 'tg')

  if (!hasTg && !hasPlain) {
    return (
      <div className={styles.empty}>
        Выберите хотя бы одну платформу выше
      </div>
    )
  }

  // if only one platform type - no tabs needed
  if (hasTg && !hasPlain) return <div className={styles.single}><RichTextEditor /></div>
  if (!hasTg && hasPlain) return <div className={styles.single}><PlainTextEditor /></div>

  return (
    <div className={styles.wrapper}>
      <div className={styles.tabs}>
        <button
          type="button"
          className={`${styles.tab} ${tab === 'tg' ? styles.active : ''}`}
          onClick={() => setTab('tg')}
        >
          Telegram
          <span className={styles.tabHint}>Markdown, форматирование</span>
        </button>
        <button
          type="button"
          className={`${styles.tab} ${tab === 'plain' ? styles.active : ''}`}
          onClick={() => setTab('plain')}
        >
          ВК / IG / Max
          <span className={styles.tabHint}>Только текст</span>
        </button>
      </div>
      <div className={styles.content}>
        {tab === 'tg' ? <RichTextEditor /> : <PlainTextEditor />}
      </div>
    </div>
  )
}
