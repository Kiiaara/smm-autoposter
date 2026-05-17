import { useState } from 'react'
import ChannelSettings from '../components/settings/ChannelSettings'
import SlotSettings from '../components/settings/SlotSettings'
import ReminderBotSettings from '../components/settings/ReminderBotSettings'
import styles from './SettingsPage.module.css'

type Tab = 'channels' | 'schedule' | 'reminders'

const TABS: { id: Tab; label: string }[] = [
  { id: 'channels', label: 'Каналы' },
  { id: 'schedule', label: 'Расписание' },
  { id: 'reminders', label: 'Бот напоминаний' },
]

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('channels')

  return (
    <div className={styles.page}>
      <div className={styles.sidebar}>
        {TABS.map(t => (
          <button
            key={t.id}
            className={`${styles.sideTab} ${tab === t.id ? styles.active : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className={styles.content}>
        {tab === 'channels' && <ChannelSettings />}
        {tab === 'schedule' && <SlotSettings />}
        {tab === 'reminders' && <ReminderBotSettings />}
      </div>
    </div>
  )
}
