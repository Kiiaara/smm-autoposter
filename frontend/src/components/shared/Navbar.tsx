import { NavLink, useNavigate } from 'react-router-dom'
import client from '../../api/client'
import styles from './Navbar.module.css'

export default function Navbar() {
  const navigate = useNavigate()

  async function logout() {
    try { await client.post('/auth/logout') } catch {}
    navigate('/login', { replace: true })
  }

  return (
    <nav className={styles.nav}>
      <div className={styles.logo}>Otlozhka ot Kiiara</div>
      <NavLink to="/posts/new" className="btn btn-primary">+ Создать пост</NavLink>
      <div className={styles.links}>
        <NavLink to="/" end className={({ isActive }) => isActive ? styles.active : ''}>Календарь</NavLink>
        <NavLink to="/drafts" className={({ isActive }) => isActive ? styles.active : ''}>Черновики</NavLink>
        <NavLink to="/stats" className={({ isActive }) => isActive ? styles.active : ''}>Статистика</NavLink>
        <NavLink to="/settings" className={({ isActive }) => isActive ? styles.active : ''}>Настройки</NavLink>
      </div>
      <button onClick={logout} className="btn btn-secondary btn-sm" style={{ marginLeft: 'auto' }}>Выйти</button>
    </nav>
  )
}
