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

  // Строим карту статусов по платформе. Если пост уже прошёл по времени
  // и таргет всё ещё pending - тоже считаем сломанным (VPN мёртв, не отправилось).
  const now = new Date()
  const scheduled = parseISO(post.scheduled_at)
  const isPast = scheduled < now
  const statusByPlatform: Record<string, 'ok' | 'fail' | 'pending'> = {}
  for (const t of post.targets || []) {
    if (t.status === 'failed') statusByPlatform[t.platform] = 'fail'
    else if (t.status === 'pending' && isPast) statusByPlatform[t.platform] = 'fail'
    else if (t.status === 'published') {
      if (statusByPlatform[t.platform] !== 'fail') statusByPlatform[t.platform] = 'ok'
    } else {
      if (!statusByPlatform[t.platform]) statusByPlatform[t.platform] = 'pending'
    }
  }
  const hasAnyFail = Object.values(statusByPlatform).includes('fail')

  return (
    <div className={`${styles.card} ${styles[`status_${post.status}`]} ${hasAnyFail ? styles.hasFail : ''}`} onClick={onClick}>
      <div className={styles.top}>
        <span className={styles.time}>{time}</span>
        <div className={styles.chips}>
          {isNoonPost && <span className={styles.chip} title="После публикации придёт ссылка в TG">🔔</span>}
          {post.platforms.map(p => {
            const st = statusByPlatform[p]
            const failed = st === 'fail'
            const title = failed
              ? `${PLATFORM_ICONS[p]}: НЕ ОПУБЛИКОВАН (ошибка или пропущено)`
              : st === 'ok'
                ? `${PLATFORM_ICONS[p]}: опубликован`
                : `${PLATFORM_ICONS[p]}: ждёт публикации`
            return (
              <span
                key={p}
                className={`${styles.chip} ${failed ? styles.chipFail : ''}`}
                style={{ color: failed ? '#ff4d4f' : PLATFORM_COLORS[p] }}
                title={title}
              >
                {failed ? '⚠' : ''}{PLATFORM_ICONS[p]}
              </span>
            )
          })}
          {post.has_poll && <span className={styles.chip} title="Есть опрос">?</span>}
        </div>
      </div>
      {post.preview_text && <p className={styles.text}>{post.preview_text}</p>}
    </div>
  )
}
