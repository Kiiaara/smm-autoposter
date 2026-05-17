import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import client from '../../api/client'
import styles from './ReminderBotSettings.module.css'

interface BotStatus {
  bot_token_set: boolean
  chat_id: string
  bot_username?: string
}

export default function ReminderBotSettings() {
  const qc = useQueryClient()
  const [token, setToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [editing, setEditing] = useState(false)

  const { data: status } = useQuery<BotStatus>({
    queryKey: ['reminder-bot-status'],
    queryFn: () => client.get('/settings/reminder-bot').then(r => r.data),
  })

  // pre-fill chat_id when status loads (token остаётся скрытым)
  useEffect(() => {
    if (status?.chat_id) setChatId(status.chat_id)
  }, [status?.chat_id])

  const isConfigured = status?.bot_token_set && status?.chat_id

  async function save() {
    setSaving(true)
    try {
      await client.put('/settings/reminder-bot', { bot_token: token, chat_id: chatId })
      toast.success('Настройки бота сохранены')
      setToken('')
      setEditing(false)
      qc.invalidateQueries({ queryKey: ['reminder-bot-status'] })
    } catch {
      toast.error('Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  async function sendTest() {
    setTesting(true)
    try {
      const r = await client.post('/settings/reminder-bot/test')
      if (r.data.ok) toast.success('Тестовое сообщение отправлено! Проверь TG')
      else toast.error(r.data.message ?? 'Ошибка отправки')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Ошибка')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className={styles.wrapper}>
      <h3 className={styles.title}>Бот напоминаний</h3>

      <div className={styles.autoRule}>
        <div className={styles.autoRuleHeader}>
          <span className={styles.autoRuleIcon}>🔔</span>
          <span className={styles.autoRuleTitle}>Автонапоминание: посты в 12:00</span>
          {isConfigured && <span className={styles.autoRuleStatus}>Активно</span>}
          {!isConfigured && <span className={styles.autoRuleInactive}>Неактивно</span>}
        </div>
        <p className={styles.autoRuleDesc}>
          Когда выходит пост запланированный на <strong>12:00</strong>, бот сразу пришлёт тебе в личку сообщение со ссылками на опубликованные посты во всех соцсетях.
        </p>
        <p className={styles.autoRuleDesc} style={{ marginTop: 6 }}>
          Удобно когда вечерний пост должен ссылаться на утренний - копируешь ссылку из напоминания и вставляешь.
        </p>
      </div>

      <p className={styles.hint}>
        Чтобы это работало - укажи токен бота и свой chat_id ниже.
      </p>

      {isConfigured && !editing ? (
        <div className={styles.statusCard}>
          <div className={styles.statusHeader}>
            <span className={styles.statusBadge}>✓ Настроено</span>
            <div className={styles.statusActions}>
              <button className="btn btn-secondary btn-sm" onClick={sendTest} disabled={testing}>
                {testing ? 'Отправляю...' : 'Отправить тест'}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>
                Изменить
              </button>
            </div>
          </div>
          <div className={styles.statusRow}>
            <span className={styles.statusLabel}>Токен:</span>
            <span className={styles.statusValue}>•••••••••••••••• (сохранён)</span>
          </div>
          <div className={styles.statusRow}>
            <span className={styles.statusLabel}>Chat ID:</span>
            <span className={styles.statusValue}>{status.chat_id}</span>
          </div>
          {status.bot_username && (
            <div className={styles.statusRow}>
              <span className={styles.statusLabel}>Бот:</span>
              <span className={styles.statusValue}>@{status.bot_username}</span>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className={styles.howto}>
            <strong>Как узнать chat_id:</strong> напиши в TG боту <code>@userinfobot</code> - он пришлёт твой ID.
          </div>
          <input
            className="input"
            type="password"
            placeholder={status?.bot_token_set ? 'Новый Bot Token (оставь пустым чтобы не менять)' : 'Bot Token (от @BotFather)'}
            value={token}
            onChange={e => setToken(e.target.value)}
          />
          <input
            className="input"
            placeholder="Твой личный Chat ID"
            value={chatId}
            onChange={e => setChatId(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || (!token && !status?.bot_token_set) || !chatId}>
              {saving ? 'Сохраняю...' : 'Сохранить'}
            </button>
            {editing && (
              <button className="btn btn-secondary" onClick={() => { setEditing(false); setToken('') }}>
                Отмена
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
