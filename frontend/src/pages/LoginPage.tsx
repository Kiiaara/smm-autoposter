import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import client from '../api/client'
import styles from './LoginPage.module.css'

type Phase = 'checking' | 'idle' | 'waiting' | 'expired'

export default function LoginPage() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('checking')
  const [deeplink, setDeeplink] = useState<string>('')
  const tokenRef = useRef<string>('')
  const pollRef = useRef<number | null>(null)
  const expiryRef = useRef<number>(0)

  // если уже залогинен - на главную
  useEffect(() => {
    client.get('/auth/me')
      .then(() => navigate('/', { replace: true }))
      .catch(() => setPhase('idle'))
  }, [navigate])

  function stopPolling() {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  useEffect(() => () => stopPolling(), [])

  async function startLogin() {
    try {
      const { data } = await client.post('/auth/bot/start')
      tokenRef.current = data.token
      setDeeplink(data.deeplink)
      expiryRef.current = Date.now() + data.expires_in * 1000
      setPhase('waiting')
      // открываем deeplink в новой вкладке
      window.open(data.deeplink, '_blank', 'noopener')
      // начинаем поллинг
      pollRef.current = window.setInterval(checkLogin, 2000)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Не удалось создать запрос на вход')
    }
  }

  async function checkLogin() {
    if (!tokenRef.current) return
    if (Date.now() > expiryRef.current) {
      stopPolling()
      setPhase('expired')
      return
    }
    try {
      const { data } = await client.get('/auth/bot/check', { params: { token: tokenRef.current } })
      if (data.approved) {
        stopPolling()
        toast.success(`Привет, ${data.first_name || 'друг'}!`)
        navigate('/', { replace: true })
      }
    } catch (e: any) {
      const status = e?.response?.status
      if (status === 403) {
        stopPolling()
        toast.error(e.response.data?.detail ?? 'Доступ запрещён')
        setPhase('idle')
      } else if (status === 404 || status === 410) {
        stopPolling()
        setPhase('expired')
      }
      // прочие ошибки - просто продолжаем поллить
    }
  }

  if (phase === 'checking') {
    return <div className={styles.wrap}><div className={styles.card}>Проверка сессии...</div></div>
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <h1 className={styles.title}>Otlozhka ot Kiiara</h1>
        <p className={styles.subtitle}>Вход через Telegram</p>

        {phase === 'idle' && (
          <>
            <button type="button" className="btn btn-primary" onClick={startLogin} style={{ minWidth: 220 }}>
              Войти через Telegram
            </button>
            <p className={styles.hint}>
              Откроется чат с ботом. Нажмите там "Старт" - и вернётесь сюда залогиненной.
            </p>
          </>
        )}

        {phase === 'waiting' && (
          <>
            <div className={styles.waitBox}>
              <div className={styles.spinner} />
              <p style={{ margin: 0 }}>Ждём подтверждения в Telegram...</p>
            </div>
            <a href={deeplink} target="_blank" rel="noopener" className="btn btn-secondary">
              Открыть бота ещё раз
            </a>
            <p className={styles.hint}>
              В чате с ботом нажмите "Старт" (или /start). Окно закроется автоматически.
            </p>
          </>
        )}

        {phase === 'expired' && (
          <>
            <p style={{ color: 'var(--danger)', margin: 0 }}>Срок ссылки истёк (10 минут).</p>
            <button type="button" className="btn btn-primary" onClick={startLogin} style={{ minWidth: 220 }}>
              Попробовать снова
            </button>
          </>
        )}

        <p className={styles.hint}>Доступ только для разрешённых пользователей.</p>
      </div>
    </div>
  )
}
