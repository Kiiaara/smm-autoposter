import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'
import { getOverview, getTopPosts, getSubscribers, getBestTime, collectTgNow, collectTtNow, getChannelTotals } from '../api/stats'
import { getChannels } from '../api/channels'
import { useQueryClient } from '@tanstack/react-query'
import styles from './StatsPage.module.css'

const PLATFORM_LABELS: Record<string, string> = { tg: 'TG', vk: 'VK', ig: 'IG', max: 'MX', tt: 'TT' }
const PLATFORM_COLORS: Record<string, string> = { tg: '#29b6f6', vk: '#4a76a8', ig: '#e1306c', max: '#ff6b35', tt: '#ff0050' }
const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

type SortBy = 'views' | 'likes' | 'reposts' | 'comments'

const SORT_LABELS: Record<SortBy, string> = {
  views: 'Просмотры',
  likes: 'Реакции',
  reposts: 'Репосты',
  comments: 'Комментарии',
}

export default function StatsPage() {
  const qc = useQueryClient()
  const [collecting, setCollecting] = useState(false)
  const [collectMsg, setCollectMsg] = useState<string>('')
  const [period, setPeriod] = useState(30)
  const [sortBy, setSortBy] = useState<SortBy>('views')

  // Диапазон дат для ручного сбора и сумм по каналам. Если пусто - работает period_days.
  const [sinceDate, setSinceDate] = useState<string>('')
  const [untilDate, setUntilDate] = useState<string>('')

  // Универсальный сбор для TG (Telethon) и TT (RapidAPI) - оба ходят через xray-туннель
  const handleCollect = async (kind: 'tg' | 'tt') => {
    setCollecting(true)
    setCollectMsg('')
    try {
      const fn = kind === 'tg' ? collectTgNow : collectTtNow
      const label = kind === 'tg' ? 'TG' : 'TikTok'
      const params: any = sinceDate
        ? { since_date: sinceDate, until_date: untilDate || undefined }
        : { period_days: period }
      const res = await fn(params)
      const ok = res.channels.filter((c: any) => c.ok).length
      const total = res.channels.length
      const posts = res.channels.reduce((sum: number, c: any) => sum + (c.posts || 0), 0)
      setCollectMsg(`${label}: собрано ${ok}/${total} каналов, ${posts} постов`)
      qc.invalidateQueries({ queryKey: ['stats-top'] })
      qc.invalidateQueries({ queryKey: ['stats-overview'] })
      qc.invalidateQueries({ queryKey: ['stats-subs'] })
      qc.invalidateQueries({ queryKey: ['channel-totals'] })
    } catch (e: any) {
      setCollectMsg(`Ошибка: ${e?.response?.data?.detail || e.message || 'unknown'}`)
    } finally {
      setCollecting(false)
    }
  }

  // Суммы просмотров/лайков по каждому каналу за период (или произвольный диапазон)
  const totalsParams = sinceDate
    ? { since_date: sinceDate, until_date: untilDate || undefined }
    : { period_days: period }
  const { data: channelTotals = [] } = useQuery({
    queryKey: ['channel-totals', totalsParams],
    queryFn: () => getChannelTotals(totalsParams),
  })
  const [topPlatform, setTopPlatform] = useState<'all' | 'tg' | 'vk' | 'tt'>('all')
  const [topChannelId, setTopChannelId] = useState<number | 'all'>('all')

  // сравнение каналов: до 2-х выбранных
  const [cmpA, setCmpA] = useState<number | ''>('')
  const [cmpB, setCmpB] = useState<number | ''>('')
  // фильтр для секции "По постам через сервис"
  const [serviceChannelId, setServiceChannelId] = useState<number | 'all'>('all')
  // выбор канала в секции "Динамика подписчиков"
  const [subsChannelId, setSubsChannelId] = useState<number | ''>('')

  const { data: overview } = useQuery({ queryKey: ['stats-overview', period], queryFn: () => getOverview(period) })
  const { data: topPosts = [] } = useQuery({
    queryKey: ['stats-top', period, sortBy, topPlatform, topChannelId],
    queryFn: () => getTopPosts({
      period_days: period,
      sort_by: sortBy,
      limit: 30,
      platform: topPlatform === 'all' ? undefined : topPlatform,
      channel_id: topChannelId === 'all' ? undefined : topChannelId,
    }),
  })
  const { data: subSeries = [] } = useQuery({ queryKey: ['stats-subs', period], queryFn: () => getSubscribers(period) })
  const { data: bestTime = [] } = useQuery({ queryKey: ['stats-best', period], queryFn: () => getBestTime(period) })
  const { data: allChannelsRaw = [] } = useQuery({ queryKey: ['channels-active'], queryFn: () => getChannels() })

  // канал в фильтре "Топ постов" - берём ВСЕ активные каналы (не только с собранным snapshot)
  const allChannels = overview?.channels ?? []
  const activeChannels = allChannelsRaw.filter((c: any) => c.is_active)
  const channelsForTopFilter = (topPlatform === 'all'
    ? activeChannels
    : activeChannels.filter((c: any) => c.platform === topPlatform)
  ).map((c: any) => ({ channel_id: c.id, name: c.name, platform: c.platform }))

  // если выбранный канал не подходит под платформу - сбросим
  if (topChannelId !== 'all' && !channelsForTopFilter.find((c: any) => c.channel_id === topChannelId)) {
    setTimeout(() => setTopChannelId('all'), 0)
  }

  // первая инициализация: в "Сравнение каналов" по умолчанию ставим первый канал
  if (cmpA === '' && allChannels.length > 0) {
    setTimeout(() => setCmpA(allChannels[0].channel_id), 0)
  }

  const cmpChannelA = allChannels.find(c => c.channel_id === cmpA)
  const cmpChannelB = allChannels.find(c => c.channel_id === cmpB)

  // сервис-посты для фильтра
  const allServicePosts = overview?.service_posts ?? []
  const filteredServicePosts = serviceChannelId === 'all'
    ? allServicePosts
    : allServicePosts.filter(sp => sp.channel_id === serviceChannelId)

  // динамика подписчиков: серии с реальными данными (>= 2 точек)
  const subsValidSeries = subSeries.filter(s => s.points.length >= 2)
  // авто-выбор первого канала с данными
  if (subsChannelId === '' && subsValidSeries.length > 0) {
    setTimeout(() => setSubsChannelId(subsValidSeries[0].channel_id), 0)
  }
  const subsSelected = subsValidSeries.find(s => s.channel_id === subsChannelId)

  // === Глобальные фильтры страницы: платформа + канал ===
  // topPlatform и topChannelId теперь управляют ВСЕЙ страницей (не только "Топ постов").
  // Каналы для выпадашки - берём все активные из /api/channels, фильтруем по платформе.
  const filteredActiveChannels = topPlatform === 'all'
    ? activeChannels
    : activeChannels.filter((c: any) => c.platform === topPlatform)

  // Фильтр списка "все посты через сервис" под глобальный канал/платформу
  const scopedServicePosts = allServicePosts.filter((sp: any) => {
    if (topPlatform !== 'all' && sp.platform !== topPlatform) return false
    if (topChannelId !== 'all' && sp.channel_id !== topChannelId) return false
    return true
  })

  // Каналы для таблицы "По каналам" - фильтруем по платформе (если выбрана)
  const scopedChannelTotals = channelTotals.filter((c: any) => {
    if (topPlatform !== 'all' && c.platform !== topPlatform) return false
    if (topChannelId !== 'all' && c.channel_id !== topChannelId) return false
    return true
  })

  // Динамика подписчиков - фильтруем ряды под глобальный канал
  const scopedSubsSeries = subsValidSeries.filter((s: any) => {
    if (topPlatform !== 'all' && s.platform !== topPlatform) return false
    if (topChannelId !== 'all' && s.channel_id !== topChannelId) return false
    return true
  })

  // Метрики сверху: если выбран конкретный канал - показываем его total из channelTotals,
  // иначе сумма по scopedChannelTotals (это точная сумма из БД, не overview с TGStat)
  const scopedMetrics = {
    posts: scopedChannelTotals.reduce((s: number, c: any) => s + c.posts_count, 0),
    views: scopedChannelTotals.reduce((s: number, c: any) => s + c.total_views, 0),
    likes: scopedChannelTotals.reduce((s: number, c: any) => s + c.total_likes, 0),
    reposts: scopedChannelTotals.reduce((s: number, c: any) => s + c.total_reposts, 0),
    comments: scopedChannelTotals.reduce((s: number, c: any) => s + c.total_comments, 0),
  }

  // Топ-посты уже фильтруются на сервере через platform+channel_id
  const [topTab, setTopTab] = useState<'all' | 'service'>('all')

  const period_days_effective = sinceDate ? undefined : period
  const exportUrl = topChannelId !== 'all'
    ? `/api/stats/posts/export.xlsx?channel_id=${topChannelId}${period_days_effective ? `&period_days=${period_days_effective}` : ''}`
    : null

  // "Через сервис" vs "Не через сервис" - для тыканья стримеру.
  // - Все посты канала (scopedChannelTotals) - тут сумма ВСЕХ постов канала за период.
  // - Через сервис (scopedServicePosts) - то что вышло у нас в редакторе.
  // - Не через сервис = вычитание.
  const serviceVsOrganic = (() => {
    // Работает когда выбран конкретный канал (или один канал в фильтре).
    // Берём тотал канала - вычитаем метрики "через сервис".
    if (scopedChannelTotals.length === 0) return null
    const totalAll = scopedChannelTotals.reduce((acc: any, c: any) => ({
      posts: acc.posts + c.posts_count,
      views: acc.views + c.total_views,
      likes: acc.likes + c.total_likes,
      reposts: acc.reposts + c.total_reposts,
      comments: acc.comments + c.total_comments,
    }), { posts: 0, views: 0, likes: 0, reposts: 0, comments: 0 })

    const totalService = scopedServicePosts.reduce((acc: any, sp: any) => ({
      posts: acc.posts + sp.posts_count,
      views: acc.views + sp.total_views,
      likes: acc.likes + sp.total_likes,
      reposts: acc.reposts + 0,  // в service_posts нет total_reposts
      comments: acc.comments + sp.avg_comments * sp.posts_count,
    }), { posts: 0, views: 0, likes: 0, reposts: 0, comments: 0 })

    if (totalService.posts === 0) return null

    const organic = {
      posts: Math.max(0, totalAll.posts - totalService.posts),
      views: Math.max(0, totalAll.views - totalService.views),
      likes: Math.max(0, totalAll.likes - totalService.likes),
      reposts: Math.max(0, totalAll.reposts - totalService.reposts),
      comments: Math.max(0, totalAll.comments - totalService.comments),
    }

    // Средние на пост - вот тут интересно тыкать стримеру
    const avg = (t: any) => ({
      views: t.posts ? Math.round(t.views / t.posts) : 0,
      likes: t.posts ? Math.round(t.likes / t.posts) : 0,
      reposts: t.posts ? Math.round(t.reposts / t.posts) : 0,
      comments: t.posts ? Math.round(t.comments / t.posts) : 0,
    })

    return {
      service: { ...totalService, avg: avg(totalService) },
      organic: { ...organic, avg: avg(organic) },
    }
  })()

  return (
    <div className={styles.page}>
      {/* Заголовок */}
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>Статистика</h1>
      </div>

      {/* Единая панель фильтров - управляет всей страницей */}
      <div className={styles.section} style={{ padding: '14px 16px' }}>
        <div className={styles.filtersRow} style={{ flexWrap: 'wrap', gap: 12 }}>
          <div className={styles.filterGroup}>
            <span className={styles.sortLabel}>Площадка:</span>
            {(['all', 'tg', 'vk', 'tt'] as const).map(p => (
              <button
                key={p}
                className={`${styles.sortBtn} ${topPlatform === p ? styles.sortBtnActive : ''}`}
                onClick={() => { setTopPlatform(p); setTopChannelId('all') }}
              >
                {p === 'all' ? 'Все' : PLATFORM_LABELS[p]}
              </button>
            ))}
          </div>
          <div className={styles.filterGroup}>
            <span className={styles.sortLabel}>Канал:</span>
            <select
              className={styles.channelSelect}
              value={topChannelId}
              onChange={e => setTopChannelId(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            >
              <option value="all">Все каналы</option>
              {filteredActiveChannels.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {PLATFORM_LABELS[c.platform]} · {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.filterGroup}>
            <span className={styles.sortLabel}>Период:</span>
            <select
              className={styles.periodSelect}
              value={sinceDate ? '' : period}
              onChange={e => { setPeriod(Number(e.target.value)); setSinceDate(''); setUntilDate('') }}
            >
              <option value={7}>7 дней</option>
              <option value={30}>30 дней</option>
              <option value={60}>60 дней</option>
              <option value={90}>90 дней</option>
              {sinceDate && <option value="">Свой</option>}
            </select>
            <span className={styles.sortLabel}>или с</span>
            <input
              type="date"
              className={styles.channelSelect}
              value={sinceDate}
              onChange={e => setSinceDate(e.target.value)}
            />
            <span className={styles.sortLabel}>по</span>
            <input
              type="date"
              className={styles.channelSelect}
              value={untilDate}
              onChange={e => setUntilDate(e.target.value)}
            />
            {sinceDate && (
              <button className={styles.clearBtn} onClick={() => { setSinceDate(''); setUntilDate('') }} title="Сбросить">×</button>
            )}
          </div>
          <div className={styles.filterGroup} style={{ marginLeft: 'auto' }}>
            <button
              className={`btn btn-primary ${styles.exportBtn}`}
              onClick={() => handleCollect('tg')}
              disabled={collecting}
              title="Собрать свежую статистику TG-каналов через VPN-туннель"
            >
              {collecting ? '⏳' : '🔄'} TG
            </button>
            <button
              className={`btn btn-primary ${styles.exportBtn}`}
              onClick={() => handleCollect('tt')}
              disabled={collecting}
              title="Собрать свежую статистику TikTok-каналов"
            >
              {collecting ? '⏳' : '🔄'} TikTok
            </button>
            {exportUrl && (
              <a href={exportUrl} className={`btn btn-primary ${styles.exportBtn}`} download>
                📥 Excel
              </a>
            )}
          </div>
        </div>
        {collectMsg && (
          <div className={styles.sortLabel} style={{ marginTop: 8 }}>{collectMsg}</div>
        )}
      </div>

      {/* Метрики - меняются под глобальный фильтр */}
      <div className={styles.metricsRow}>
        <MetricCard label="Постов" value={scopedMetrics.posts} />
        <MetricCard label="Просмотров" value={scopedMetrics.views} />
        <MetricCard label="Реакций" value={scopedMetrics.likes} />
        <MetricCard label="Комментариев" value={scopedMetrics.comments} />
      </div>

      {/* Таблица "По каналам" - главная секция */}
      <Section title={topChannelId === 'all' ? 'По каналам за период' : 'Итого по каналу'}>
        {scopedChannelTotals.length === 0 ? (
          <p className={styles.empty}>
            Нет данных за период. Собери статистику кнопками "🔄 TG / TikTok" сверху.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>Канал</th>
                  <th className={styles.num}>Постов</th>
                  <th className={styles.num}>Просмотры</th>
                  <th className={styles.num}>Реакции</th>
                  <th className={styles.num}>Репосты</th>
                  <th className={styles.num}>Комменты</th>
                </tr>
              </thead>
              <tbody>
                {scopedChannelTotals.map((c: any) => (
                  <tr key={c.channel_id} className={styles.clickable} onClick={() => setTopChannelId(c.channel_id)}>
                    <td>
                      <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[c.platform] }}>
                        {PLATFORM_LABELS[c.platform]}
                      </span>
                      {' '}{c.name}
                    </td>
                    <td className={styles.num}>{c.posts_count.toLocaleString('ru')}</td>
                    <td className={styles.num}>{c.total_views.toLocaleString('ru')}</td>
                    <td className={styles.num}>{c.total_likes.toLocaleString('ru')}</td>
                    <td className={styles.num}>{c.total_reposts.toLocaleString('ru')}</td>
                    <td className={styles.num}>{c.total_comments.toLocaleString('ru')}</td>
                  </tr>
                ))}
                {scopedChannelTotals.length > 1 && (
                  <tr className={styles.rowTotal}>
                    <td>Итого</td>
                    <td className={styles.num}>{scopedMetrics.posts.toLocaleString('ru')}</td>
                    <td className={styles.num}>{scopedMetrics.views.toLocaleString('ru')}</td>
                    <td className={styles.num}>{scopedMetrics.likes.toLocaleString('ru')}</td>
                    <td className={styles.num}>{scopedMetrics.reposts.toLocaleString('ru')}</td>
                    <td className={styles.num}>{scopedMetrics.comments.toLocaleString('ru')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* Через сервис vs Обычные посты - таблица для сравнения */}
      {serviceVsOrganic && (
        <Section title="Через наш сервис vs обычные посты">
          <div style={{ overflowX: 'auto' }}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th></th>
                  <th className={styles.num}>Постов</th>
                  <th className={styles.num}>Просмотры<small>всего / в среднем</small></th>
                  <th className={styles.num}>Реакции<small>всего / в среднем</small></th>
                  <th className={styles.num}>Репосты</th>
                  <th className={styles.num}>Комменты<small>всего / в среднем</small></th>
                </tr>
              </thead>
              <tbody>
                <tr className={styles.rowHighlight}>
                  <td><b>🚀 Через сервис</b></td>
                  <td className={styles.num}><b>{serviceVsOrganic.service.posts.toLocaleString('ru')}</b></td>
                  <td className={styles.num}>
                    <b>{serviceVsOrganic.service.views.toLocaleString('ru')}</b>
                    <small>{serviceVsOrganic.service.avg.views.toLocaleString('ru')} / пост</small>
                  </td>
                  <td className={styles.num}>
                    <b>{serviceVsOrganic.service.likes.toLocaleString('ru')}</b>
                    <small>{serviceVsOrganic.service.avg.likes.toLocaleString('ru')} / пост</small>
                  </td>
                  <td className={styles.num}>{serviceVsOrganic.service.reposts.toLocaleString('ru')}</td>
                  <td className={styles.num}>
                    <b>{serviceVsOrganic.service.comments.toLocaleString('ru')}</b>
                    <small>{serviceVsOrganic.service.avg.comments.toLocaleString('ru')} / пост</small>
                  </td>
                </tr>
                <tr>
                  <td>Обычные (не через сервис)</td>
                  <td className={styles.num}>{serviceVsOrganic.organic.posts.toLocaleString('ru')}</td>
                  <td className={styles.num}>
                    {serviceVsOrganic.organic.views.toLocaleString('ru')}
                    <small>{serviceVsOrganic.organic.avg.views.toLocaleString('ru')} / пост</small>
                  </td>
                  <td className={styles.num}>
                    {serviceVsOrganic.organic.likes.toLocaleString('ru')}
                    <small>{serviceVsOrganic.organic.avg.likes.toLocaleString('ru')} / пост</small>
                  </td>
                  <td className={styles.num}>{serviceVsOrganic.organic.reposts.toLocaleString('ru')}</td>
                  <td className={styles.num}>
                    {serviceVsOrganic.organic.comments.toLocaleString('ru')}
                    <small>{serviceVsOrganic.organic.avg.comments.toLocaleString('ru')} / пост</small>
                  </td>
                </tr>
                {(() => {
                  const s = serviceVsOrganic.service.avg
                  const o = serviceVsOrganic.organic.avg
                  const diff = (a: number, b: number) => {
                    if (!b) return '—'
                    const pct = Math.round(((a - b) / b) * 100)
                    return `${pct >= 0 ? '+' : ''}${pct}%`
                  }
                  const clr = (a: number, b: number) => a > b ? '#4caf50' : a < b ? '#f44336' : 'inherit'
                  return (
                    <tr className={styles.rowTotal}>
                      <td>Разница (среднее на пост)</td>
                      <td className={styles.num}>—</td>
                      <td className={styles.num} style={{ color: clr(s.views, o.views) }}>{diff(s.views, o.views)}</td>
                      <td className={styles.num} style={{ color: clr(s.likes, o.likes) }}>{diff(s.likes, o.likes)}</td>
                      <td className={styles.num}>—</td>
                      <td className={styles.num} style={{ color: clr(s.comments, o.comments) }}>{diff(s.comments, o.comments)}</td>
                    </tr>
                  )
                })()}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Динамика подписчиков - фильтрована под канал/платформу */}
      <Section title="Динамика подписчиков">
        {scopedSubsSeries.length === 0 ? (
          <p className={styles.empty}>Нужно минимум 2 точки данных. Подожди пока соберётся (раз в час) или обнови статистику.</p>
        ) : (
          <SubscribersChart series={scopedSubsSeries} />
        )}
      </Section>

      {/* Сравнение A vs B - в отдельной секции */}
      <Section title="Сравнение каналов A vs B">
        {allChannels.length < 2 ? (
          <p className={styles.empty}>Для сравнения нужно минимум 2 канала со статистикой</p>
        ) : (
          <>
            <div className={styles.filtersRow}>
              <div className={styles.filterGroup}>
                <span className={styles.sortLabel}>A:</span>
                <select
                  className={styles.channelSelect}
                  value={cmpA}
                  onChange={e => setCmpA(e.target.value === '' ? '' : Number(e.target.value))}
                >
                  {allChannels.map(c => (
                    <option key={c.channel_id} value={c.channel_id}>
                      {PLATFORM_LABELS[c.platform]} · {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.filterGroup}>
                <span className={styles.sortLabel}>B:</span>
                <select
                  className={styles.channelSelect}
                  value={cmpB}
                  onChange={e => setCmpB(e.target.value === '' ? '' : Number(e.target.value))}
                >
                  <option value="">— не выбран —</option>
                  {allChannels.filter(c => c.channel_id !== cmpA).map(c => (
                    <option key={c.channel_id} value={c.channel_id}>
                      {PLATFORM_LABELS[c.platform]} · {c.name}
                    </option>
                  ))}
                </select>
                {cmpB !== '' && (
                  <button className={styles.clearBtn} onClick={() => setCmpB('')} title="Убрать">×</button>
                )}
              </div>
            </div>
            <ChannelCompareTable a={cmpChannelA} b={cmpChannelB} />
          </>
        )}
      </Section>

      {/* Топ постов + вкладки Все / Через сервис */}
      <Section title="Топ постов">
        <div className={styles.sortTabs}>
          <button
            className={`${styles.sortTab} ${topTab === 'all' ? styles.sortTabActive : ''}`}
            onClick={() => setTopTab('all')}
          >
            Все посты канала
          </button>
          <button
            className={`${styles.sortTab} ${topTab === 'service' ? styles.sortTabActive : ''}`}
            onClick={() => setTopTab('service')}
          >
            Только через наш сервис
          </button>
        </div>

        {topTab === 'all' ? (
          <>
            <div className={styles.sortTabs}>
              {(['views', 'likes', 'reposts', 'comments'] as SortBy[]).map(s => (
                <button
                  key={s}
                  className={`${styles.sortTab} ${sortBy === s ? styles.sortTabActive : ''}`}
                  onClick={() => setSortBy(s)}
                >
                  {SORT_LABELS[s]}
                </button>
              ))}
            </div>
            {topPosts.length === 0 ? (
              <p className={styles.empty}>Нет данных за период. Собери статистику кнопками сверху.</p>
            ) : (
              <PostsExplorer posts={topPosts} sortBy={sortBy} />
            )}
          </>
        ) : (
          scopedServicePosts.length === 0 ? (
            <p className={styles.empty}>За период нет постов, опубликованных через наш сервис для этого фильтра</p>
          ) : (
            <ServicePostsTable items={scopedServicePosts} />
          )
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

function ChannelCompareTable({ a, b }: { a?: any; b?: any }) {
  if (!a) return null
  const rows: { label: string; key: string }[] = [
    { label: 'Подписчиков', key: 'subscribers' },
    { label: 'Постов в канале', key: 'posts_count' },
    { label: 'Ср. просмотры', key: 'avg_views' },
    { label: 'Ср. лайки', key: 'avg_likes' },
  ]

  function diff(av: number, bv: number) {
    if (!bv) return ''
    const d = av - bv
    if (d === 0) return '='
    const pct = bv > 0 ? Math.round((d / bv) * 100) : 0
    const sign = d > 0 ? '+' : ''
    return `${sign}${d.toLocaleString('ru')} (${sign}${pct}%)`
  }

  return (
    <div className={styles.cmpTable}>
      <div className={styles.cmpHeader}>
        <div />
        <CmpChannelHead ch={a} />
        {b && <CmpChannelHead ch={b} />}
        {b && <div className={styles.cmpDiffHead}>A − B</div>}
      </div>
      {rows.map(r => {
        const av = a[r.key] as number
        const bv = b ? (b[r.key] as number) : 0
        const diffStr = b ? diff(av, bv) : ''
        const diffClass = !b ? '' : av > bv ? styles.diffPositive : av < bv ? styles.diffNegative : ''
        return (
          <div key={r.key} className={styles.cmpRow}>
            <div className={styles.cmpLabel}>{r.label}</div>
            <div className={styles.cmpValue}>{av.toLocaleString('ru')}</div>
            {b && <div className={styles.cmpValue}>{bv.toLocaleString('ru')}</div>}
            {b && <div className={`${styles.cmpDiff} ${diffClass}`}>{diffStr}</div>}
          </div>
        )
      })}
    </div>
  )
}

function CmpChannelHead({ ch }: { ch: any }) {
  return (
    <div className={styles.cmpHeadCell}>
      <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[ch.platform] }}>
        {PLATFORM_LABELS[ch.platform]}
      </span>
      <span className={styles.cmpChannelName}>{ch.name}</span>
    </div>
  )
}

function ServicePostsTable({ items }: { items: any[] }) {
  if (items.length === 0) return <p className={styles.empty}>Нет данных</p>
  // если один - показываем как карточку, если несколько - как компактную таблицу
  if (items.length === 1) {
    const sp = items[0]
    return (
      <div className={styles.singleChannelCard}>
        <div className={styles.channelHead}>
          <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[sp.platform] }}>
            {PLATFORM_LABELS[sp.platform]}
          </span>
          <span className={styles.channelName}>{sp.name}</span>
        </div>
        <div className={styles.statsGrid}>
          <Stat label="Постов" value={sp.posts_count} />
          <Stat label="Всего просмотров" value={sp.total_views} />
          <Stat label="Ср. просмотры" value={sp.avg_views} />
          <Stat label="Ср. лайки" value={sp.avg_likes} />
          <Stat label="Ср. комментарии" value={sp.avg_comments} />
        </div>
      </div>
    )
  }
  return (
    <div className={styles.servicePostsTable}>
      <div className={styles.serviceHeader}>
        <span>Канал</span>
        <span className={styles.numCol}>Постов</span>
        <span className={styles.numCol}>Всего просм.</span>
        <span className={styles.numCol}>Ср. просм.</span>
        <span className={styles.numCol}>Ср. лайки</span>
        <span className={styles.numCol}>Ср. комм.</span>
      </div>
      {items.map(sp => (
        <div key={sp.channel_id} className={styles.serviceRow}>
          <div className={styles.serviceCell}>
            <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[sp.platform] }}>
              {PLATFORM_LABELS[sp.platform]}
            </span>
            <span>{sp.name}</span>
          </div>
          <div className={styles.numCol}>{sp.posts_count.toLocaleString('ru')}</div>
          <div className={styles.numCol}>{sp.total_views.toLocaleString('ru')}</div>
          <div className={styles.numCol}>{sp.avg_views.toLocaleString('ru')}</div>
          <div className={styles.numCol}>{sp.avg_likes.toLocaleString('ru')}</div>
          <div className={styles.numCol}>{sp.avg_comments.toLocaleString('ru')}</div>
        </div>
      ))}
    </div>
  )
}

function PostsExplorer({ posts, sortBy }: { posts: any[]; sortBy: SortBy }) {
  const [selectedIdx, setSelectedIdx] = useState(0)
  // если posts поменялись (фильтр) - сбрасываем на 0
  const safeIdx = selectedIdx >= posts.length ? 0 : selectedIdx
  const selected = posts[safeIdx]

  function metricValue(p: any) {
    switch (sortBy) {
      case 'views': return p.views
      case 'likes': return p.likes
      case 'reposts': return p.reposts
      case 'comments': return p.comments
    }
  }
  function metricIcon() {
    switch (sortBy) {
      case 'views': return '👁'
      case 'likes': return '❤'
      case 'reposts': return '↗'
      case 'comments': return '💬'
    }
  }

  // iframe идёт на наш прокси - бэк скачивает t.me embed через xray (VPN),
  // и юзеру превью грузится без необходимости иметь свой VPN включённым.
  function embedUrl(p: any): string | null {
    if (!p?.url) return null
    const m = p.url.match(/t\.me\/([^/]+)\/(\d+)/)
    if (!m) return null
    return `/api/stats/tg/embed/${m[1]}/${m[2]}`
  }

  const embed = embedUrl(selected)

  return (
    <div className={styles.postsExplorer}>
      <div className={styles.postsList}>
        {posts.map((p, i) => (
          <button
            key={`${p.post_id}-${p.channel_name}-${i}`}
            className={`${styles.postListRow} ${i === safeIdx ? styles.postListRowActive : ''}`}
            onClick={() => setSelectedIdx(i)}
          >
            <div className={styles.postListMain}>
              <div className={styles.postListMeta}>
                <span className={styles.platformBadge} style={{ background: PLATFORM_COLORS[p.platform] }}>
                  {PLATFORM_LABELS[p.platform]}
                </span>
                <span className={styles.postListChannel}>{p.channel_name}</span>
                <span className={styles.postListDate}>{format(parseISO(p.published_at), 'd MMM, HH:mm', { locale: ru })}</span>
              </div>
              <div className={styles.postListPreview}>
                {p.preview || p.title || '(без текста)'}
              </div>
            </div>
            <div className={styles.postListMetric}>
              <span className={styles.postListMetricIcon}>{metricIcon()}</span>
              <span className={styles.postListMetricValue}>{metricValue(p).toLocaleString('ru')}</span>
            </div>
          </button>
        ))}
      </div>
      <div className={styles.postsPreview}>
        {embed ? (
          <iframe
            key={embed}
            src={embed}
            className={styles.postsPreviewIframe}
            scrolling="no"
            frameBorder={0}
          />
        ) : selected ? (
          <div className={styles.postsPreviewFallback}>
            <div className={styles.postsPreviewText}>{selected.preview || selected.title || '(нет текста)'}</div>
            {selected.url && (
              <a href={selected.url} target="_blank" rel="noopener" className="btn btn-secondary">
                Открыть пост ↗
              </a>
            )}
          </div>
        ) : (
          <div className={styles.empty}>Выберите пост слева</div>
        )}
        {selected && (
          <div className={styles.postsPreviewStats}>
            <div><span>👁 Просмотры</span><b>{selected.views.toLocaleString('ru')}</b></div>
            <div><span>❤ Реакции</span><b>{selected.likes.toLocaleString('ru')}</b></div>
            <div><span>↗ Репосты</span><b>{selected.reposts.toLocaleString('ru')}</b></div>
            <div><span>💬 Комментарии</span><b>{selected.comments.toLocaleString('ru')}</b></div>
          </div>
        )}
      </div>
    </div>
  )
}

function SubscribersChart({ series }: { series: any[] }) {
  // показываем только каналы у которых есть минимум 2 точки
  const valid = series.filter(s => s.points.length >= 2)
  if (valid.length === 0) return null

  return (
    <div className={styles.miniChartsGrid}>
      {valid.map(s => (
        <MiniChannelChart key={s.channel_id} series={s} />
      ))}
    </div>
  )
}

function MiniChannelChart({ series }: { series: any }) {
  const W = 300, H = 120, PAD_X = 8, PAD_TOP = 10, PAD_BOTTOM = 18
  const pts = series.points
  const color = PLATFORM_COLORS[series.platform] || '#7b61ff'
  const svgRef = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<{ x: number; y: number; idx: number } | null>(null)

  const values = pts.map((p: any) => p.subscribers)
  const maxY = Math.max(...values)
  const minY = Math.min(...values)
  const rangeY = Math.max(maxY - minY, 1)
  const xStep = (W - PAD_X * 2) / Math.max(pts.length - 1, 1)

  const first = values[0]
  const last = values[values.length - 1]
  const diff = last - first
  const diffPct = first > 0 ? (diff / first) * 100 : 0

  const coords: { x: number; y: number; point: any }[] = pts.map((p: any, i: number) => ({
    x: PAD_X + i * xStep,
    y: PAD_TOP + (H - PAD_TOP - PAD_BOTTOM) - ((p.subscribers - minY) / rangeY) * (H - PAD_TOP - PAD_BOTTOM),
    point: p,
  }))
  const polyPoints = coords.map((c) => `${c.x},${c.y}`).join(' ')
  const areaPoints = `${PAD_X},${H - PAD_BOTTOM} ${polyPoints} ${PAD_X + (pts.length - 1) * xStep},${H - PAD_BOTTOM}`

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    // переводим клиентские координаты в координаты viewBox
    const xInVB = ((e.clientX - rect.left) / rect.width) * W
    // ближайший индекс
    const idx = Math.max(0, Math.min(coords.length - 1, Math.round((xInVB - PAD_X) / xStep)))
    setHover({ x: coords[idx].x, y: coords[idx].y, idx })
  }

  const hoverPoint = hover ? coords[hover.idx] : null
  // позиция tooltip в % от ширины SVG (т.к. preserveAspectRatio=none — viewBox растягивается)
  const tooltipLeftPct = hoverPoint ? (hoverPoint.x / W) * 100 : 0

  return (
    <div className={styles.miniChart}>
      <div className={styles.miniChartHead}>
        <span className={styles.platformBadge} style={{ background: color }}>
          {PLATFORM_LABELS[series.platform]}
        </span>
        <span className={styles.miniChartName}>{series.name}</span>
      </div>
      <div className={styles.miniChartValues}>
        <span className={styles.miniChartCurrent}>{last.toLocaleString('ru')}</span>
        <span className={diff >= 0 ? styles.diffPositive : styles.diffNegative}>
          {diff >= 0 ? '+' : ''}{diff.toLocaleString('ru')}
          {first > 0 && ` (${diff >= 0 ? '+' : ''}${diffPct.toFixed(1)}%)`}
        </span>
      </div>
      <div className={styles.miniSvgWrap}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className={styles.miniSvg}
          preserveAspectRatio="none"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          <polygon points={areaPoints} fill={color} opacity="0.15" />
          <polyline fill="none" stroke={color} strokeWidth="2" points={polyPoints} />
          {hoverPoint && (
            <>
              <line x1={hoverPoint.x} x2={hoverPoint.x} y1={PAD_TOP} y2={H - PAD_BOTTOM} stroke={color} strokeWidth="1" opacity="0.5" strokeDasharray="3 3" />
              <circle cx={hoverPoint.x} cy={hoverPoint.y} r="4" fill={color} stroke="#fff" strokeWidth="1.5" />
            </>
          )}
        </svg>
        {hoverPoint && (
          <div
            className={styles.miniTooltip}
            style={{ left: `${tooltipLeftPct}%` }}
          >
            <div className={styles.miniTooltipValue}>{hoverPoint.point.subscribers.toLocaleString('ru')}</div>
            <div className={styles.miniTooltipDate}>{hoverPoint.point.date}</div>
          </div>
        )}
      </div>
      <div className={styles.miniChartDates}>
        <span>{pts[0].date}</span>
        <span>{pts[pts.length - 1].date}</span>
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
