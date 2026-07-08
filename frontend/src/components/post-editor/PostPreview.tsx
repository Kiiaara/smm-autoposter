import { useState } from 'react'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useQuery } from '@tanstack/react-query'
import { getChannels } from '../../api/channels'
import { useEditorStore } from '../../store/editorStore'
import type { Platform, FormatRange } from '../../types'
import styles from './PostPreview.module.css'

const PLATFORM_DEFAULTS: Record<Platform, string> = {
  tg: 'Ваш канал',
  vk: 'Ваша группа',
  ig: 'username',
  max: 'Ваш канал',
  tt: 'Ваш TikTok',
}

const TABS: { id: Platform; label: string }[] = [
  { id: 'tg', label: 'Telegram' },
  { id: 'vk', label: 'ВКонтакте' },
  { id: 'ig', label: 'Instagram' },
  { id: 'max', label: 'Max' },
]

export default function PostPreview() {
  const { selectedNetworks, selectedChannels, title, textTgHtml, textPlain, mediaPaths, pollDraft } = useEditorStore()
  const available = TABS.filter(t => selectedNetworks.includes(t.id))
  const [tab, setTab] = useState<Platform>('tg')

  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: () => getChannels() })

  if (available.length === 0) {
    return <div className={styles.empty}>Выберите платформу для предпросмотра</div>
  }

  const current = available.find(t => t.id === tab) ?? available[0]
  const now = format(new Date(), 'HH:mm')
  const dateStr = format(new Date(), 'd MMM', { locale: ru })

  // first selected channel of current platform
  const channelForPlatform = channels.find(ch => ch.platform === current.id && selectedChannels.includes(ch.id))
  const channelName = channelForPlatform?.name || PLATFORM_DEFAULTS[current.id]

  return (
    <div className={styles.wrapper}>
      <div className={styles.tabs}>
        {available.map(t => (
          <button key={t.id} type="button"
            className={`${styles.tab} ${current.id === t.id ? styles.active : ''}`}
            onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div className={styles.preview}>
        {current.id === 'tg' && <TgPreview title={title} html={textTgHtml} media={mediaPaths} poll={pollDraft} time={now} channelName={channelName} />}
        {current.id === 'vk' && <VkPreview title={title} text={textPlain} media={mediaPaths} poll={pollDraft} date={dateStr} channelName={channelName} />}
        {current.id === 'ig' && <IgPreview title={title} text={textPlain} media={mediaPaths} channelName={channelName} />}
        {current.id === 'max' && <MaxPreview title={title} text={textPlain} media={mediaPaths} date={dateStr} channelName={channelName} />}
      </div>
    </div>
  )
}

// ── Telegram ──────────────────────────────────────
function TgPreview({ title, html, media, poll, time, channelName }: any) {
  const initial = (channelName || 'К')[0].toUpperCase()
  const hasMedia = media?.length > 0
  const hasContent = !!(html && html.replace(/<[^>]+>/g, '').trim())
  const hasText = (hasContent || title) && (!poll || !poll.tg_no_text)
  const showTextBubble = hasMedia || hasText
  const showEmptyHint = !hasMedia && !hasText && !poll

  return (
    <div className={styles.tgPhone}>
      <div className={styles.tgTopBar}>
        <div className={styles.tgAvatar}>{initial}</div>
        <div className={styles.tgChannelInfo}>
          <div className={styles.tgChannelName}>{channelName || 'Канал'}</div>
          <div className={styles.tgChannelSubs}>1 234 подписчика</div>
        </div>
      </div>
      <div className={styles.tgFeed}>
        {showTextBubble && (
          <div className={styles.tgBubble}>
            {hasMedia && (
              <div className={styles.tgMediaWrap}>
                <div className={`${styles.tgMediaGrid} ${gridClass(media.length)}`}>
                  {media.slice(0, 4).map((p: string, i: number) => (
                    <img key={i} src={`/${p}`} className={`${styles.tgMediaImg} ${media.length === 1 ? styles.tall : ''}`} alt="" />
                  ))}
                </div>
              </div>
            )}
            {hasText && (
              <div className={styles.tgText}>
                {title && <div className={styles.tgTitle}>{title}</div>}
                {html && <div dangerouslySetInnerHTML={{ __html: html }} />}
              </div>
            )}
            <div className={styles.tgMeta}>
              <span className={styles.tgViews}>👁 1.2K</span>
              <span className={styles.tgTime}>{time}</span>
            </div>
          </div>
        )}
        {showEmptyHint && (
          <div className={styles.tgBubble}>
            <div className={styles.noContent}>Текст или медиа не добавлены</div>
            <div className={styles.tgMeta}>
              <span className={styles.tgViews}>👁 1.2K</span>
              <span className={styles.tgTime}>{time}</span>
            </div>
          </div>
        )}
        {poll && (
          <div className={styles.tgBubble} style={{ marginTop: 4 }}>
            <div className={styles.tgPoll}>
              <div className={styles.tgPollQ}>{poll.question || 'Вопрос опроса'}</div>
              {(poll.options?.length ? poll.options : ['Вариант 1', 'Вариант 2']).map((o: string, i: number) => (
                <div key={i} className={styles.tgPollOption}>{o || `Вариант ${i + 1}`}</div>
              ))}
              <div className={styles.tgPollMeta}>{poll.is_anonymous ? 'Анонимный опрос' : 'Публичный опрос'}</div>
            </div>
          </div>
        )}
        <div className={styles.tgReactions}>
          <span className={styles.tgReaction}>👍 24</span>
          <span className={styles.tgReaction}>🔥 8</span>
          <span className={styles.tgReaction}>❤️ 12</span>
        </div>
      </div>
    </div>
  )
}

function gridClass(n: number) {
  if (n === 1) return styles.one
  if (n === 2) return styles.two
  if (n === 3) return styles.three
  return styles.many
}

// извлекаем URL статьи VK из текста + slug для заголовка
function extractVkArticle(text: string): { url: string; slug: string } | null {
  if (!text) return null
  const match = text.match(/https?:\/\/(?:m\.)?vk\.com\/@[^\s]+/i)
  if (!match) return null
  const url = match[0]
  // slug = всё после последнего "-" или после "@..."
  const slugRaw = url.split('vk.com/@')[1] || ''
  // делаем читаемое название из slug: убираем префикс "group-", меняем "-" на пробелы
  const slug = slugRaw.split('-').slice(1).join(' ') || slugRaw.replace(/-/g, ' ')
  return { url, slug: slug.charAt(0).toUpperCase() + slug.slice(1) }
}

// ── VKontakte (mobile) ────────────────────────────
function VkPreview({ title, text, media, poll, channelName }: any) {
  const initial = (channelName || 'Г')[0].toUpperCase()
  const article = extractVkArticle(text)
  // текст без URL статьи (если она была)
  const cleanText = article ? text.replace(article.url, '').trim() : text
  return (
    <div className={styles.vkCard}>
      <div className={styles.vkHeader}>
        <div className={styles.vkAvatar}>{initial}</div>
        <div>
          <div className={styles.vkNameRow}>
            <span className={styles.vkName}>{channelName || 'Группа'}</span>
            <span className={styles.vkVerified}>✓</span>
          </div>
          <div className={styles.vkDate}>20 ч назад</div>
        </div>
        <span className={styles.vkMore}>···</span>
      </div>
      {media?.length > 0 && (
        <div className={styles.vkMedia}>
          <img src={`/${media[0]}`} className={styles.vkImg} alt="" />
          {media.length > 1 && <div className={styles.vkImgCount}>1/{media.length}</div>}
        </div>
      )}
      {(title || cleanText) && (
        <div className={styles.vkText}>
          {title && <div className={styles.vkTitle}>{title}</div>}
          {cleanText}
        </div>
      )}
      {article && (
        <div className={styles.vkArticle}>
          <div className={styles.vkArticleCover}>
            <span className={styles.vkArticleIcon}>📄</span>
          </div>
          <div className={styles.vkArticleBody}>
            <div className={styles.vkArticleLabel}>Статья</div>
            <div className={styles.vkArticleTitle}>{article.slug || 'Статья VK'}</div>
            <div className={styles.vkArticleHost}>vk.com</div>
          </div>
        </div>
      )}
      {!title && !cleanText && !media?.length && !article && <div className={styles.vkText} style={{ color: '#bbb' }}>Текст поста...</div>}
      {poll && (
        <div className={styles.vkPoll}>
          <div className={styles.vkPollQ}>{poll.question || 'Вопрос опроса'}</div>
          {(poll.options?.length ? poll.options : ['Вариант 1', 'Вариант 2']).map((o: string, i: number) => (
            <div key={i} className={styles.vkPollOpt}>{o || `Вариант ${i + 1}`}</div>
          ))}
        </div>
      )}
      <div className={styles.vkActions}>
        <span className={styles.vkAction}><span className={styles.vkActionIcon}>♡</span> 249</span>
        <span className={styles.vkAction}><span className={styles.vkActionIcon}>💬</span> 64</span>
        <span className={styles.vkAction}><span className={styles.vkActionIcon}>↗</span> 365</span>
      </div>
    </div>
  )
}

// ── Instagram ─────────────────────────────────────
function IgPreview({ title, text, media, channelName }: any) {
  const username = (channelName || 'username').toLowerCase().replace(/\s+/g, '_')
  const initial = (channelName || 'U')[0].toUpperCase()
  return (
    <div className={styles.igCard}>
      <div className={styles.igHeader}>
        <div className={styles.igAvatar}>
          <div className={styles.igAvatarInner}>{initial}</div>
        </div>
        <span className={styles.igUsername}>{username}</span>
        <span className={styles.igMore}>···</span>
      </div>
      {media?.length > 0 ? (
        <div className={styles.igMedia}>
          <img src={`/${media[0]}`} className={styles.igImg} alt="" />
        </div>
      ) : (
        <div style={{ background: '#f0f0f0', aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 13 }}>
          Фото не добавлено
        </div>
      )}
      <div className={styles.igActions}>
        <span className={styles.igActionBtn}>🤍</span>
        <span className={styles.igActionBtn}>💬</span>
        <span className={styles.igActionBtn}>✈️</span>
        <span className={`${styles.igActionBtn} ${styles.igSave}`}>🔖</span>
      </div>
      <div className={styles.igLikes}>1 234 отметки «Нравится»</div>
      {(title || text) && (
        <div className={styles.igCaption}>
          <span className={styles.igCaptionUser}>{username}</span>
          {title && <strong>{title}{'\n'}</strong>}
          {text}
        </div>
      )}
      <div className={styles.igDate}>Только что</div>
    </div>
  )
}

// ── Max (Telegram-like with blue theme) ──────────
function MaxPreview({ title, text, media, channelName }: any) {
  const initial = (channelName || 'К')[0].toUpperCase()
  const hasMedia = media?.length > 0
  const hasText = title || text
  return (
    <div className={styles.maxPhone}>
      <div className={styles.maxTopBar}>
        <span className={styles.maxBackIcon}>‹</span>
        <div className={styles.maxAvatar}>{initial}</div>
        <div className={styles.maxChannelInfo}>
          <div className={styles.maxName}>{channelName || 'Канал'}</div>
          <div className={styles.maxSubs}>1 086 519 подписчиков</div>
        </div>
        <span className={styles.maxMore}>⋮</span>
      </div>
      <div className={styles.maxFeed}>
        <div className={styles.maxBubble}>
          {hasMedia && <img src={`/${media[0]}`} className={styles.maxImg} alt="" />}
          {hasText && (
            <div className={styles.maxText}>
              {title && <div className={styles.maxTitle}>{title}</div>}
              {text}
            </div>
          )}
          {!hasMedia && !hasText && <div className={styles.maxText} style={{ color: '#bbb' }}>Текст или медиа...</div>}
          <div className={styles.maxMeta}>
            <span className={styles.maxViews}>👁 98.3K</span>
            <span className={styles.maxTime}>23:41</span>
          </div>
          <div className={styles.maxReactions}>
            <span className={styles.maxReaction}>👍 176</span>
            <span className={styles.maxReaction}>🔥 87</span>
            <span className={styles.maxReaction}>❤️ 31</span>
          </div>
        </div>
      </div>
      <div className={styles.maxSubscribe}>Подписаться</div>
    </div>
  )
}

// ── HTML renderer ─────────────────────────────────
function toHtml(text: string, ranges: FormatRange[], s: any): string {
  if (!text) return ''
  if (!ranges?.length) return esc(text)
  const sorted = [...ranges].sort((a, b) => a.start - b.start)
  let res = '', pos = 0
  for (const r of sorted) {
    if (r.start > pos) res += esc(text.slice(pos, r.start))
    const chunk = esc(text.slice(r.start, r.end))
    switch (r.type) {
      case 'bold': res += `<strong>${chunk}</strong>`; break
      case 'italic': res += `<em>${chunk}</em>`; break
      case 'strike': res += `<s>${chunk}</s>`; break
      case 'code': res += `<code>${chunk}</code>`; break
      case 'spoiler': res += `<span class="${s.spoilerText}">${chunk}</span>`; break
      case 'link': res += `<a href="${r.url}" target="_blank">${chunk}</a>`; break
      default: res += chunk
    }
    pos = r.end
  }
  if (pos < text.length) res += esc(text.slice(pos))
  return res.replace(/\n/g, '<br>')
}

function esc(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
