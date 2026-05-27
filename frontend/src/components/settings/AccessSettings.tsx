import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { getAllowedUsers, addAllowedUser, removeAllowedUser } from '../../api/auth'
import styles from './AccessSettings.module.css'

type Mode = 'email' | 'tg'

export default function AccessSettings() {
  const qc = useQueryClient()
  const [mode, setMode] = useState<Mode>('email')
  const [tgId, setTgId] = useState('')
  const [email, setEmail] = useState('')
  const [label, setLabel] = useState('')

  const { data: users = [], isLoading } = useQuery({ queryKey: ['allowed-users'], queryFn: getAllowedUsers })

  const addMutation = useMutation({
    mutationFn: () => {
      if (mode === 'tg') {
        return addAllowedUser({ tg_id: Number(tgId), label: label || undefined })
      }
      return addAllowedUser({ email: email.trim().toLowerCase(), label: label || undefined })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['allowed-users'] })
      toast.success('Доступ выдан')
      setTgId(''); setEmail(''); setLabel('')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка'),
  })

  const removeMutation = useMutation({
    mutationFn: (id: number) => removeAllowedUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['allowed-users'] })
      toast.success('Доступ отозван')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка'),
  })

  function handleAdd() {
    if (mode === 'tg') {
      const num = Number(tgId)
      if (!num || isNaN(num)) {
        toast.error('TG ID должен быть числом')
        return
      }
    } else {
      const e = email.trim().toLowerCase()
      if (!e.includes('@') || !e.includes('.')) {
        toast.error('Некорректный email')
        return
      }
    }
    addMutation.mutate()
  }

  return (
    <div className={styles.wrapper}>
      <h3>Доступ</h3>
      <p className={styles.hint}>
        Только пользователи из этого списка могут заходить в сервис.
      </p>

      <div className={styles.modeTabs}>
        <button
          type="button"
          className={`${styles.modeTab} ${mode === 'email' ? styles.modeTabActive : ''}`}
          onClick={() => setMode('email')}
        >
          По email
        </button>
        <button
          type="button"
          className={`${styles.modeTab} ${mode === 'tg' ? styles.modeTabActive : ''}`}
          onClick={() => setMode('tg')}
        >
          По TG ID
        </button>
      </div>

      <div className={styles.addForm}>
        {mode === 'tg' ? (
          <input
            className="input"
            placeholder="TG ID (число)"
            value={tgId}
            onChange={e => setTgId(e.target.value.replace(/\D/g, ''))}
          />
        ) : (
          <input
            className="input"
            type="email"
            placeholder="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
        )}
        <input
          className="input"
          placeholder="Имя (необязательно)"
          value={label}
          onChange={e => setLabel(e.target.value)}
        />
        <button
          className="btn btn-primary"
          onClick={handleAdd}
          disabled={(mode === 'tg' ? !tgId : !email) || addMutation.isPending}
        >
          {addMutation.isPending ? 'Добавляю...' : 'Добавить'}
        </button>
      </div>

      {mode === 'tg' && (
        <p className={styles.hint} style={{ marginTop: -4 }}>
          Чтобы узнать свой TG ID, напиши{' '}
          <a href="https://t.me/userinfobot" target="_blank" rel="noopener">@userinfobot</a> в Telegram.
        </p>
      )}

      {isLoading ? (
        <p className={styles.empty}>Загрузка...</p>
      ) : users.length === 0 ? (
        <p className={styles.empty}>Никого нет в списке</p>
      ) : (
        <div className={styles.list}>
          {users.map(u => (
            <div key={u.tg_id} className={styles.item}>
              <div className={styles.itemMain}>
                <div className={styles.itemLabel}>
                  {u.label || '(без имени)'}
                  {u.is_self && <span className={styles.selfBadge}>это ты</span>}
                </div>
                <div className={styles.itemId}>
                  {u.email
                    ? `Email: ${u.email}`
                    : `TG ID: ${u.tg_id}`}
                </div>
              </div>
              {!u.is_self && (
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => {
                    if (confirm(`Удалить доступ для ${u.label || u.email || u.tg_id}?`)) {
                      removeMutation.mutate(u.tg_id)
                    }
                  }}
                  disabled={removeMutation.isPending}
                >
                  Удалить
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
