import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'
import { getOverview, getTopPosts, getSubscribers, getBestTime } from '../api/stats'
import styles from './StatsPage.module.css'

const PLATFORM_LABELS: Record<string, string> = { tg: 'TG', vk: 'VK', ig: 'IG', max: 'MX' }
const PLATFORM_COLORS: Record<string, string> = { tg: '#29b6f6', vk: '#4a76a8', ig: '#e1306c', max: '#ff6b35' }
const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

type SortBy = 'views' | 'likes' | 'reposts' | 'comments'

export default function StatsPage() {
  const [period, setPeriod] = useState(30)
  const [sortBy, setSortBy] = useState<SortBy>('views')

  const { data: overview } = useQuery({ queryKey: ['stats-overview', period], queryFn: () => getOverview(period) })
  const { data: topPosts = [] } = useQuery({ queryKey: ['stats-top', period, sortBy], queryFn: () => getTopPosts({ period_days: period, sort_by: sortBy, limit: 15 }) })
  const { data: subSeries = [] } = useQuery({ queryKey: ['stats-subs', period], queryFn: () => getSubscribers(period) })
  const { data: bestTime = [] } = useQuery({ queryKey: ['stats-best', period], queryFn: () => getBestTime(period) })

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>Статистика</h1>
        <select className={styles.periodSelect} value={period} onChange={e => setPeriod(Number(e.target.value))}>
          <option value={7}>Последние 7 дней</option>
          <option value={30}>Последние 30 дней</option>
          <option value={60}>Последние 60 дней</option>
          <option value={90}>Последние 90 дней</option>
        </select>
      </div>

      {/* Общие метрики */}
      <div className={styles.metricsRow}>
        <MetricCard label="Постов" value={overview?.total_posts ?? 0} />
        <MetricCard label="Просмотров" value={overview?.total_views ?? 0} />
        <MetricCard label="Лайков" value={overview?.total_likes ?? 0} />
        <MetricCard label="Комментариев" value={overview?.total_comments ?? 0} />
      </div>

      {/* Каналы - сравнение */}
      <Section title="Сравнение каналов">
        {overview?.channels.length === 0 ? (
          <p className={styles.empty}>Пока нет опубликованных постов с собранной статистикой</p>
        ) : (
          <div className={styles.channelGrid}>
            {overview?.channels.map(ch => (
              <div key={ch.channel_id} className={styles.channelCard}>
                <div className={styles.channelHead}>
                  <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[ch.platform] }}>
                    {PLATFORM_LABELS[ch.platform]}
                  </span>
                  <span className={styles.channelName}>{ch.name}</span>
                </div>
                <div className={styles.channelStats}>
                  <Stat label="Подписчиков" value={ch.subscribers} />
                  <Stat label="Постов в канале" value={ch.posts_count} />
                  <Stat label="Ср. просмотры" value={ch.avg_views} />
                  <Stat label="Ср. лайки" value={ch.avg_likes} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* По нашим постам */}
      <Section title="По постам через сервис">
        {!overview?.service_posts || overview.service_posts.length === 0 ? (
          <p className={styles.empty}>За период не было опубликованных постов через сервис</p>
        ) : (
          <div className={styles.channelGrid}>
            {overview.service_posts.map(sp => (
              <div key={sp.channel_id} className={styles.channelCard}>
                <div className={styles.channelHead}>
                  <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[sp.platform] }}>
                    {PLATFORM_LABELS[sp.platform]}
                  </span>
                  <span className={styles.channelName}>{sp.name}</span>
                </div>
                <div className={styles.channelStats}>
                  <Stat label="Постов" value={sp.posts_count} />
                  <Stat label="Всего просмотров" value={sp.total_views} />
                  <Stat label="Ср. просмотры" value={sp.avg_views} />
                  <Stat label="Ср. лайки" value={sp.avg_likes} />
                  <Stat label="Ср. комментарии" value={sp.avg_comments} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* График подписчиков */}
      <Section title="Динамика подписчиков">
        {subSeries.every(s => s.points.length < 2) ? (
          <p className={styles.empty}>Нужно минимум 2 точки данных. Подожди пока соберётся (раз в час)</p>
        ) : (
          <SubscribersChart series={subSeries} />
        )}
      </Section>

      {/* Топ постов */}
      <Section title="Топ постов">
        <div className={styles.sortBar}>
          <span className={styles.sortLabel}>Сортировать по:</span>
          {(['views', 'likes', 'reposts', 'comments'] as SortBy[]).map(s => (
            <button
              key={s}
              className={`${styles.sortBtn} ${sortBy === s ? styles.sortBtnActive : ''}`}
              onClick={() => setSortBy(s)}
            >
              {s === 'views' && 'Просмотры'}
              {s === 'likes' && 'Лайки'}
              {s === 'reposts' && 'Репосты'}
              {s === 'comments' && 'Комменты'}
            </button>
          ))}
        </div>
        {topPosts.length === 0 ? (
          <p className={styles.empty}>Нет данных за выбранный период</p>
        ) : (
          <div className={styles.postsTable}>
            <div className={styles.postsHeader}>
              <span>Пост</span>
              <span>Канал</span>
              <span>Дата</span>
              <span className={styles.numCol}>👁</span>
              <span className={styles.numCol}>❤️</span>
              <span className={styles.numCol}>↗️</span>
              <span className={styles.numCol}>💬</span>
            </div>
            {topPosts.map(p => (
              <div key={p.post_id + p.channel_name} className={styles.postRow}>
                <div className={styles.postCell}>
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noopener" className={styles.postLink}>
                      {p.title || p.preview || 'Без названия'}
                    </a>
                  ) : (
                    <span>{p.title || p.preview || 'Без названия'}</span>
                  )}
                </div>
                <div className={styles.postCell}>
                  <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[p.platform] }}>
                    {PLATFORM_LABELS[p.platform]}
                  </span>
                  {p.channel_name}
                </div>
                <div className={styles.postCell}>{format(parseISO(p.published_at), 'd MMM HH:mm', { locale: ru })}</div>
                <div className={styles.numCol}>{p.views.toLocaleString('ru')}</div>
                <div className={styles.numCol}>{p.likes.toLocaleString('ru')}</div>
                <div className={styles.numCol}>{p.reposts.toLocaleString('ru')}</div>
                <div className={styles.numCol}>{p.comments.toLocaleString('ru')}</div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Лучшее время */}
      <Section title="Лучшее время для публикаций">
        {bestTime.length === 0 ? (
          <p className={styles.empty}>Нужно больше опубликованных постов чтобы построить тепловую карту</p>
        ) : (
          <BestTimeHeatmap data={bestTime} />
        )}
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: any }) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      {children}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.metric}>
      <div className={styles.metricValue}>{value.toLocaleString('ru')}</div>
      <div className={styles.metricLabel}>{label}</div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.stat}>
      <div className={styles.statValue}>{value.toLocaleString('ru')}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  )
}

function SubscribersChart({ series }: { series: any[] }) {
  const W = 760, H = 240, PAD = 36
  const allPoints = series.flatMap(s => s.points)
  if (allPoints.length === 0) return null

  const allDates = Array.from(new Set(allPoints.map((p: any) => p.date))).sort()
  const maxY = Math.max(...allPoints.map((p: any) => p.subscribers))
  const minY = Math.min(...allPoints.map((p: any) => p.subscribers))
  const rangeY = Math.max(maxY - minY, 1)

  const xStep = (W - PAD * 2) / Math.max(allDates.length - 1, 1)

  return (
    <div className={styles.chartWrap}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.chart}>
        {[0, 0.25, 0.5, 0.75, 1].map(t => (
          <line key={t} x1={PAD} x2={W - PAD} y1={PAD + (H - PAD * 2) * t} y2={PAD + (H - PAD * 2) * t} stroke="#2e3340" strokeWidth="1" />
        ))}
        {series.map(s => {
          const color = PLATFORM_COLORS[s.platform] || '#7b61ff'
          const pts = s.points.map((p: any) => {
            const x = PAD + allDates.indexOf(p.date) * xStep
            const y = PAD + (H - PAD * 2) - ((p.subscribers - minY) / rangeY) * (H - PAD * 2)
            return `${x},${y}`
          }).join(' ')
          return <polyline key={s.channel_id} fill="none" stroke={color} strokeWidth="2.5" points={pts} />
        })}
      </svg>
      <div className={styles.chartLegend}>
        {series.map(s => (
          <div key={s.channel_id} className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: PLATFORM_COLORS[s.platform] }} />
            {s.name}
            {s.points.length > 0 && <strong> {s.points[s.points.length - 1].subscribers.toLocaleString('ru')}</strong>}
          </div>
        ))}
      </div>
    </div>
  )
}

function BestTimeHeatmap({ data }: { data: any[] }) {
  const maxViews = Math.max(...data.map(d => d.avg_views), 1)
  const cellMap = new Map<string, any>()
  data.forEach(d => cellMap.set(`${d.day_of_week}-${d.hour}`, d))

  return (
    <div className={styles.heatmap}>
      <div className={styles.heatmapHourRow}>
        <span className={styles.heatmapCorner} />
        {Array.from({ length: 24 }, (_, h) => (
          <span key={h} className={styles.heatmapHour}>{h}</span>
        ))}
      </div>
      {DAY_NAMES.map((dn, dow) => (
        <div key={dow} className={styles.heatmapRow}>
          <span className={styles.heatmapDay}>{dn}</span>
          {Array.from({ length: 24 }, (_, h) => {
            const cell = cellMap.get(`${dow}-${h}`)
            const intensity = cell ? cell.avg_views / maxViews : 0
            const bg = cell ? `rgba(123, 97, 255, ${0.15 + intensity * 0.85})` : 'transparent'
            return (
              <span
                key={h}
                className={styles.heatmapCell}
                style={{ background: bg }}
                title={cell ? `${dn} ${h}:00 - ${Math.round(cell.avg_views)} просмотров (${cell.posts} постов)` : ''}
              >
                {cell && Math.round(cell.avg_views) >= 1000 ? '★' : ''}
              </span>
            )
          })}
        </div>
      ))}
    </div>
  )
}
