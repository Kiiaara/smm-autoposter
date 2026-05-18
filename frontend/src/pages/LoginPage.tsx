import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import client from '../api/client'
import styles from './LoginPage.module.css'

const BOT_USERNAME = 'posts_tpabomah_bot'

export default function LoginPage() {
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [checking, setChecking] = useState(true)

  // если уже залогинен - сразу на главную
  useEffect(() => {
    client.get('/auth/me')
      .then(() => navigate('/', { replace: true }))
      .catch(() => setChecking(false))
  }, [navigate])

  // подгружаем TG-виджет
  useEffect(() => {
    if (checking) return
    const el = containerRef.current
    if (!el) return
    el.innerHTML = ''

    // глобальный коллбэк, который вызовет виджет TG после логина
    ;(window as any).onTelegramAuth = async (user: any) => {
      try {
        await client.post('/auth/telegram', user)
        toast.success(`Привет, ${user.first_name || 'пользователь'}!`)
        navigate('/', { replace: true })
      } catch (e: any) {
        toast.error(e?.response?.data?.detail ?? 'Ошибка авторизации')
      }
    }

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.async = true
    script.setAttribute('data-telegram-login', BOT_USERNAME)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-radius', '8')
    script.setAttribute('data-onauth', 'onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    el.appendChild(script)

    return () => {
      delete (window as any).onTelegramAuth
    }
  }, [checking, navigate])

  if (checking) {
    return <div className={styles.wrap}><div className={styles.card}>Проверка сессии...</div></div>
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <h1 className={styles.title}>Otlozhka ot Kiiara</h1>
        <p className={styles.subtitle}>Вход через Telegram</p>
        <div ref={containerRef} className={styles.widget} />
        <p className={styles.hint}>Доступ только для разрешённых пользователей.</p>
      </div>
    </div>
  )
}
