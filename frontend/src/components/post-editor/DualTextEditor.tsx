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

  // подсчитаем какие именно платформы plain
  const plainPlatforms = selectedNetworks.filter(n => n !== 'tg')
  const plainLabel = plainPlatforms.map(p => p.toUpperCase()).join(' · ')

  return (
    <div className={styles.wrapper}>
      <div className={styles.pills}>
        <button
          type="button"
          className={`${styles.pill} ${tab === 'tg' ? styles.active : ''} ${styles.pillTg}`}
          onClick={() => setTab('tg')}
        >
          <span className={styles.pillIcon}>TG</span>
          Telegram
        </button>
        <button
          type="button"
          className={`${styles.pill} ${tab === 'plain' ? styles.active : ''} ${styles.pillPlain}`}
          onClick={() => setTab('plain')}
        >
          <span className={styles.pillIcon}>{plainPlatforms[0]?.toUpperCase()}</span>
          {plainLabel}
        </button>
      </div>
      <div className={styles.content}>
        {tab === 'tg' ? <RichTextEditor /> : <PlainTextEditor />}
      </div>
    </div>
  )
}
