import { useState } from 'react'
import { format, addDays, parseISO, isToday } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { publishPost, deletePost } from '../../api/posts'
import type { CalendarDay, CalendarPost } from '../../types'
import styles from './WeekCalendar.module.css'

const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

interface Props {
  weekStart: Date
  days: CalendarDay[]
  onPostClick: (id: number) => void
  onSlotClick: (date: string, time: string) => void
}

interface CardItem {
  kind: 'slot' | 'post'
  time: string
  post?: CalendarPost
}

export default function WeekCalendar({ weekStart, days, onPostClick, onSlotClick }: Props) {
  return (
    <div className={styles.board}>
      {DAY_NAMES.map((dayName, i) => {
        const d = addDays(weekStart, i)
        const today = isToday(d)
        const day = days[i]
        const items = buildItems(day)

        return (
          <div key={i} className={styles.column}>
            <div className={`${styles.colHeader} ${today ? styles.colHeaderToday : ''}`}>
              <span className={styles.dayName}>{dayName} {format(d, 'd', { locale: ru })}</span>
            </div>

            <div className={styles.colBody}>
              {items.length === 0 && <div className={styles.emptyState}>Нет публикаций</div>}

              {items.map((it, idx) => it.kind === 'slot'
                ? <EmptySlotCard key={`s-${idx}`} time={it.time} onClick={() => onSlotClick(format(d, 'yyyy-MM-dd'), it.time)} />
                : <PostCard key={`p-${it.post!.id}`} post={it.post!} onClick={() => onPostClick(it.post!.id)} />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** Build interleaved list of empty slots + posts, sorted by time. */
function buildItems(day?: CalendarDay): CardItem[] {
  if (!day) return []
  const items: CardItem[] = []

  // free schedule slots
  for (const slot of day.slots) {
    if (slot.is_free) items.push({ kind: 'slot', time: slot.slot_time })
  }
  // actual posts
  for (const post of day.posts) {
    const t = format(parseISO(post.scheduled_at), 'HH:mm')
    items.push({ kind: 'post', time: t, post })
  }

  return items.sort((a, b) => a.time.localeCompare(b.time))
}

function EmptySlotCard({ time, onClick }: { time: string; onClick: () => void }) {
  return (
    <button type="button" className={styles.emptySlot} onClick={onClick}>
      <span className={styles.plusIcon}>+</span>
      <span className={styles.slotTime}>{time}</span>
    </button>
  )
}

const PLATFORM_INFO: Record<string, { label: string; bg: string }> = {
  tg: { label: 'TG', bg: '#29b6f6' },
  vk: { label: 'VK', bg: '#4a76a8' },
  ig: { label: 'IG', bg: '#e1306c' },
  max: { label: 'MX', bg: '#ff6b35' },
}

function PostCard({ post, onClick }: { post: CalendarPost; onClick: () => void }) {
  const time = format(parseISO(post.scheduled_at), 'HH:mm')
  const [expanded, setExpanded] = useState(false)
  const qc = useQueryClient()

  const publishMutation = useMutation({
    mutationFn: () => publishPost(post.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
      toast.success('Запущена публикация')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePost(post.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
      toast.success('Удалено')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка удаления'),
  })

  const isDraft = post.status === 'draft'

  // Вычисляем фактический статус из таргетов - post.status обманчив
  // (может быть 'published' даже если один из каналов упал, и наоборот - 'scheduled'
  // хотя таргет уже давно 'failed'). Плюс просроченные pending считаем failed.
  const now = new Date()
  const scheduledDt = new Date(post.scheduled_at)
  const isPast = scheduledDt < now
  const targets = post.targets || []
  const hasFailed = targets.some(t => t.status === 'failed' || (t.status === 'pending' && isPast))
  const hasOk = targets.some(t => t.status === 'published')
  const allOk = targets.length > 0 && targets.every(t => t.status === 'published')

  let statusIcon: string
  let statusClass: string
  if (isDraft) {
    statusIcon = '✎'
    statusClass = styles.iconDraft
  } else if (hasFailed) {
    statusIcon = hasOk ? '⚠' : '✕'
    statusClass = styles.iconFailed
  } else if (allOk) {
    statusIcon = '✓'
    statusClass = styles.iconPublished
  } else {
    statusIcon = '⏱'
    statusClass = styles.iconScheduled
  }

  const text = post.preview_text?.trim() || (post.has_poll ? 'Опрос (без описания)' : 'Без текста')
  const hasPlatforms = post.platforms.length > 0

  return (
    <div className={`${styles.postCard} ${isDraft ? styles.postCardDraft : ''} ${hasFailed ? styles.postCardFailed : ''}`} onClick={onClick}>
      <div className={styles.cardHeader}>
        <span className={`${styles.statusIcon} ${statusClass}`}>{statusIcon}</span>
        <span className={styles.cardTime}>{time}</span>
        <span className={styles.kindLabel}>{isDraft ? 'Черновик' : post.has_poll ? 'Опрос' : 'Пост'}</span>
      </div>

      {!expanded && (
        <p className={`${styles.cardText} ${!post.preview_text?.trim() ? styles.cardTextEmpty : ''}`}>
          {text}
        </p>
      )}

      {expanded && (
        <>
          <div className={styles.expandedText}>
            {post.preview_text || (post.has_poll ? 'Опрос без описания' : 'Текст не заполнен')}
          </div>

          {post.targets && post.targets.length > 0 && (
            <div className={styles.targetsList}>
              {post.targets.map((t, i) => (
                <div key={i} className={styles.targetRow}>
                  <span className={styles.platformBadge} style={{ background: PLATFORM_INFO[t.platform]?.bg }}>
                    {PLATFORM_INFO[t.platform]?.label || t.platform}
                  </span>
                  <span className={styles.targetName}>{t.channel_name}</span>
                  {t.status === 'published' && <span className={styles.targetOk}>✓ опубликован</span>}
                  {t.status === 'pending' && <span className={styles.targetPending}>⏱ в очереди</span>}
                  {t.status === 'failed' && <span className={styles.targetFail}>✕ ошибка</span>}
                  {t.url && (
                    <a href={t.url} target="_blank" rel="noopener" className={styles.targetLink} onClick={e => e.stopPropagation()}>
                      ссылка
                    </a>
                  )}
                  {t.error && (
                    <div className={styles.targetError}>{t.error}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          <button
            type="button"
            className={styles.republishBtn}
            onClick={e => { e.stopPropagation(); publishMutation.mutate() }}
            disabled={publishMutation.isPending}
          >
            {publishMutation.isPending ? 'Публикую...' : '↻ Опубликовать сейчас'}
          </button>
          <button
            type="button"
            className={styles.deleteBtn}
            onClick={e => {
              e.stopPropagation()
              if (confirm('Удалить этот пост?')) deleteMutation.mutate()
            }}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Удаляю...' : '🗑 Удалить пост'}
          </button>
        </>
      )}

      {!expanded && (
        <div className={styles.cardFooter}>
          {post.targets && post.targets.length > 0 ? (
            post.targets.map((t, i) => {
              const info = PLATFORM_INFO[t.platform]
              const failed = t.status === 'failed' || (t.status === 'pending' && isPast)
              const title = failed
                ? `${info?.label || t.platform} · ${t.channel_name}: НЕ ОПУБЛИКОВАН`
                : t.status === 'published'
                  ? `${info?.label || t.platform} · ${t.channel_name}: опубликован`
                  : `${info?.label || t.platform} · ${t.channel_name}: ждёт публикации`
              return (
                <span key={i} className={`${styles.channelChip} ${failed ? styles.channelChipFail : ''}`} title={title}>
                  <span className={styles.platformBadge} style={{ background: failed ? '#ff4d4f' : info?.bg }}>
                    {failed ? '⚠' : ''}{info?.label || t.platform}
                  </span>
                  <span className={styles.channelChipName}>{t.channel_name}</span>
                </span>
              )
            })
          ) : hasPlatforms ? (
            post.platforms.map(p => {
              const info = PLATFORM_INFO[p]
              return (
                <span key={p} className={styles.platformBadge} style={{ background: info?.bg }}>
                  {info?.label || p}
                </span>
              )
            })
          ) : (
            <span className={styles.noPlatform}>Каналы не выбраны</span>
          )}
        </div>
      )}

      <button
        type="button"
        className={styles.expandBtn}
        onClick={e => { e.stopPropagation(); setExpanded(v => !v) }}
      >
        {expanded ? 'Свернуть' : 'Подробнее'}
      </button>
    </div>
  )
}
