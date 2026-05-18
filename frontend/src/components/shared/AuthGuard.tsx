import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import client from '../../api/client'

interface Props {
  children: React.ReactNode
}

export default function AuthGuard({ children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const [state, setState] = useState<'checking' | 'ok' | 'no'>('checking')

  useEffect(() => {
    client.get('/auth/me')
      .then(() => setState('ok'))
      .catch(() => {
        setState('no')
        navigate('/login', { replace: true, state: { from: location.pathname } })
      })
  }, [navigate, location.pathname])

  if (state === 'checking') {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text2)' }}>Проверка авторизации...</div>
  }
  if (state === 'no') return null
  return <>{children}</>
}
