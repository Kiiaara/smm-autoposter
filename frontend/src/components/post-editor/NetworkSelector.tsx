import type { Platform } from '../../types'
import { useEditorStore } from '../../store/editorStore'
import styles from './NetworkSelector.module.css'

const NETWORKS: { id: Platform; label: string }[] = [
  { id: 'tg', label: 'Telegram' },
  { id: 'vk', label: 'ВКонтакте' },
  { id: 'ig', label: 'Instagram' },
  { id: 'max', label: 'Max' },
]

export default function NetworkSelector() {
  const { selectedNetworks, toggleNetwork } = useEditorStore()

  return (
    <div className={styles.wrapper}>
      <label className={styles.label}>Платформы</label>
      <div className={styles.chips}>
        {NETWORKS.map(n => (
          <button
            key={n.id}
            type="button"
            className={`${styles.chip} ${styles[`chip_${n.id}`]} ${selectedNetworks.includes(n.id) ? styles.active : ''}`}
            onClick={() => toggleNetwork(n.id)}
          >
            {n.label}
          </button>
        ))}
      </div>
    </div>
  )
}
