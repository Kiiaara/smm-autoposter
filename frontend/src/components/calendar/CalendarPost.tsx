import { format, parseISO } from 'date-fns'
import type { CalendarPost } from '../../types'
import styles from './CalendarPost.module.css'

const PLATFORM_COLORS: Record<string, string> = {
  tg: '#29b6f6', vk: '#4a76a8', ig: '#e1306c', max: '#ff6b35', tt: '#ff0050',
}
const PLATFORM_ICONS: Record<string, string> = {
  tg: 'TG', vk: 'VK', ig: 'IG', max: 'MX', tt: 'TT',
}

interface Props {
  post: CalendarPost
  onClick: () => void
}

export default function CalendarPostCard({ post, onClick }: Props) {
  const time = format(parseISO(post.scheduled_at), 'HH:mm')
  const isNoonPost = time === '12:00'
  return (
    <div className={`${styles.card} ${styles[`status_${post.status}`]}`} onClick={onClick}>
      <div className={styles.top}>
        <span className={styles.time}>{time}</span>
        <div className={styles.chips}>
          {isNoonPost && <span className={styles.chip} title="После публикации придёт ссылка в TG">🔔</span>}
          {post.platforms.map(p => (
            <span key={p} className={styles.chip} style={{ color: PLATFORM_COLORS[p] }}>
              {PLATFORM_ICONS[p]}
            </span>
          ))}
          {post.has_poll && <span className={styles.chip} title="Есть опрос">?</span>}
        </div>
      </div>
      {post.preview_text && <p className={styles.text}>{post.preview_text}</p>}
    </div>
  )
}
