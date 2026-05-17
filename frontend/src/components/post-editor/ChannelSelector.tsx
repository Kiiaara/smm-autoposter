import { useQuery } from '@tanstack/react-query'
import { getChannels } from '../../api/channels'
import { useEditorStore } from '../../store/editorStore'
import type { Channel } from '../../types'
import styles from './ChannelSelector.module.css'

export default function ChannelSelector() {
  const { selectedNetworks, selectedChannels, setSelectedChannels } = useEditorStore()

  const { data: channels = [] } = useQuery({
    queryKey: ['channels'],
    queryFn: () => getChannels(),
  })

  const filtered = channels.filter(ch => selectedNetworks.includes(ch.platform) && ch.is_active)

  if (filtered.length === 0) return null

  function toggle(id: number) {
    setSelectedChannels(
      selectedChannels.includes(id)
        ? selectedChannels.filter(i => i !== id)
        : [...selectedChannels, id]
    )
  }

  const PLATFORM_LABELS: Record<string, string> = { tg: 'Telegram', vk: 'ВК', ig: 'Instagram', max: 'Max' }

  const grouped = selectedNetworks.reduce<Record<string, Channel[]>>((acc, net) => {
    acc[net] = filtered.filter(ch => ch.platform === net)
    return acc
  }, {})

  return (
    <div className={styles.wrapper}>
      <label className={styles.label}>Каналы</label>
      {Object.entries(grouped).map(([platform, chs]) => chs.length > 0 && (
        <div key={platform} className={styles.group}>
          <span className={`platform-chip chip-${platform}`}>{PLATFORM_LABELS[platform]}</span>
          <div className={styles.channels}>
            {chs.map(ch => (
              <label key={ch.id} className={`${styles.channel} ${selectedChannels.includes(ch.id) ? styles.active : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedChannels.includes(ch.id)}
                  onChange={() => toggle(ch.id)}
                />
                {ch.name}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
