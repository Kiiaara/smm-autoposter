import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import client from '../api/client'
import styles from './LoginPage.module.css'

type Phase = 'checking' | 'email' | 'code'

export default function LoginPage() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('checking')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const codeInputRef = useRef<HTMLInputElement>(null)

  // если уже залогинен - на главную
  useEffect(() => {
    client.get('/auth/me')
      .then(() => navigate('/', { replace: true }))
      .catch(() => setPhase('email'))
  }, [navigate])

  async function requestCode(e: React.FormEvent) {
    e.preventDefault()
    const cleaned = email.trim().toLowerCase()
    if (!cleaned.includes('@') || !cleaned.includes('.')) {
      toast.error('Введите корректный email')
      return
    }
    setSubmitting(true)
    try {
      await client.post('/auth/email/request', { email: cleaned })
      setEmail(cleaned)
      setPhase('code')
      toast.success('Код отправлен на почту')
      setTimeout(() => codeInputRef.current?.focus(), 100)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Не удалось отправить код')
    } finally {
      setSubmitting(false)
    }
  }

  async function verifyCode(e: React.FormEvent) {
    e.preventDefault()
    if (code.length !== 6) {
      toast.error('Код должен быть из 6 цифр')
      return
    }
    setSubmitting(true)
    try {
      await client.post('/auth/email/verify', { email, code })
      toast.success('Вход выполнен')
      navigate('/', { replace: true })
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Неверный код')
    } finally {
      setSubmitting(false)
    }
  }

  if (phase === 'checking') {
    return <div className={styles.wrap}><div className={styles.card}>Проверка сессии...</div></div>
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <h1 className={styles.title}>Otlozhka ot Kiiara</h1>

        {phase === 'email' && (
          <form onSubmit={requestCode} className={styles.form}>
            <p className={styles.subtitle}>Вход по почте</p>
            <input
              type="email"
              className="input"
              placeholder="your@email.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoFocus
              required
              autoComplete="email"
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !email}
            >
              {submitting ? 'Отправляем...' : 'Получить код'}
            </button>
            <p className={styles.hint}>
              Доступ только для разрешённых пользователей. Код придёт на почту, действителен 5 минут.
            </p>
          </form>
        )}

        {phase === 'code' && (
          <form onSubmit={verifyCode} className={styles.form}>
            <p className={styles.subtitle}>Код отправлен на<br/><b>{email}</b></p>
            <input
              ref={codeInputRef}
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              className={`input ${styles.codeInput}`}
              placeholder="000000"
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              required
              autoComplete="one-time-code"
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || code.length !== 6}
            >
              {submitting ? 'Проверяем...' : 'Войти'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => { setPhase('email'); setCode('') }}
            >
              Другой email
            </button>
            <p className={styles.hint}>
              Не пришло? Проверьте папку "Спам". Код жив 5 минут.
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
