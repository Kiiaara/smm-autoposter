import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getPost } from '../api/posts'
import { getChannels } from '../api/channels'
import { useEditorStore } from '../store/editorStore'
import PostEditor from '../components/post-editor/PostEditor'
import type { Platform } from '../types'

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
