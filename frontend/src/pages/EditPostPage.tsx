import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getPost } from '../api/posts'
import { getChannels } from '../api/channels'
import { useEditorStore } from '../store/editorStore'
import PostEditor from '../components/post-editor/PostEditor'
import type { Platform, FormatRange } from '../types'

// Конвертация legacy формата (text + ranges) → HTML для редактирования старых постов
function legacyRangesToHtml(text: string, ranges: FormatRange[]): string {
  if (!ranges || ranges.length === 0) return escapeHtml(text).replace(/\n/g, '<br>')
  const n = text.length
  const activeAt: Set<string>[] = Array.from({ length: n + 1 }, () => new Set())
  const linkAt: (string | null)[] = Array(n + 1).fill(null)
  const TAG: Record<string, string> = {
    bold: 'b', italic: 'i', underline: 'u', strike: 's', code: 'code', spoiler: 'tg-spoiler',
  }
  for (const r of ranges) {
    const s = Math.max(0, r.start)
    const e = Math.min(n, r.end)
    if (e <= s) continue
    if (r.type === 'link') {
      for (let i = s; i < e; i++) linkAt[i] = r.url || ''
    } else if (TAG[r.type]) {
      for (let i = s; i < e; i++) activeAt[i].add(r.type)
    }
  }
  const ORDER = ['bold', 'italic', 'underline', 'strike', 'spoiler', 'code']
  const out: string[] = []
  let prevActive = new Set<string>()
  let prevLink: string | null = null
  const linkBuf: string[] = []
  const flushLink = () => {
    if (prevLink !== null) {
      out.push(`<a href="${escapeAttr(prevLink)}">`)
      out.push(...linkBuf)
      out.push('</a>')
      linkBuf.length = 0
      prevLink = null
    }
  }
  for (let i = 0; i <= n; i++) {
    const curActive = i < n ? activeAt[i] : new Set<string>()
    const curLink = i < n ? linkAt[i] : null
    const activeChanged = !setsEqual(curActive, prevActive)
    if (activeChanged) {
      flushLink()
      for (const t of [...ORDER].reverse()) {
        if (prevActive.has(t) && !curActive.has(t)) out.push(`</${TAG[t]}>`)
      }
      for (const t of ORDER) {
        if (curActive.has(t) && !prevActive.has(t)) out.push(`<${TAG[t]}>`)
      }
      prevActive = curActive
    }
    if (curLink !== prevLink) {
      flushLink()
      prevLink = curLink
    }
    if (i < n) {
      const ch = text[i] === '\n' ? '<br>' : escapeHtml(text[i])
      if (prevLink !== null) linkBuf.push(ch)
      else out.push(ch)
    }
  }
  flushLink()
  for (const t of [...ORDER].reverse()) if (prevActive.has(t)) out.push(`</${TAG[t]}>`)
  return out.join('')
}
function escapeHtml(s: string) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }
function escapeAttr(s: string) { return escapeHtml(s).replace(/"/g, '&quot;') }
function setsEqual<T>(a: Set<T>, b: Set<T>) {
  if (a.size !== b.size) return false
  for (const x of a) if (!b.has(x)) return false
  return true
}

export default function EditPostPage() {
  const { id } = useParams<{ id: string }>()
  const postId = Number(id)

  const { data: post } = useQuery({
    queryKey: ['post', postId],
    queryFn: () => getPost(postId),
    enabled: !!postId,
  })

  const { data: channels = [] } = useQuery({
    queryKey: ['channels'],
    queryFn: () => getChannels(),
  })

  useEffect(() => {
    if (!post || channels.length === 0) return
    const store = useEditorStore.getState()
    store.reset()
    store.setTitle(post.title ?? '')
    // Приоритет: новый HTML. Если его нет - конвертируем legacy ranges → HTML
    const html = post.text_tg_html
      ?? (post.text_tg ? legacyRangesToHtml(post.text_tg, post.text_tg_ranges ?? []) : '')
    store.setTextTgHtml(html)
    store.setTextTg(post.text_tg ?? '')
    store.setTextTgRanges(post.text_tg_ranges ?? [])
    store.setTextPlain(post.text_plain ?? '')
    store.setMediaPaths(post.media_paths ?? [])
    if (post.poll_json) store.setPollDraft(post.poll_json as any)
    if (post.scheduled_at) store.setScheduledAt(post.scheduled_at.slice(0, 16))

    const channelIds = post.targets.map(t => t.channel_id)
    store.setSelectedChannels(channelIds)

    // derive platforms from selected channels
    const platforms = new Set<Platform>()
    for (const t of post.targets) {
      const ch = channels.find(c => c.id === t.channel_id)
      if (ch) platforms.add(ch.platform)
    }
    // toggle each derived platform on
    platforms.forEach(p => store.toggleNetwork(p))
  }, [post?.id, channels.length])

  if (!post) return <div style={{ padding: 24, color: 'var(--text2)' }}>Загрузка...</div>

  return <PostEditor editPostId={postId} />
}
