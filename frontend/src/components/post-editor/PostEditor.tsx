import { useNavigate } from 'react-router-dom'
import { format, startOfWeek, parseISO } from 'date-fns'
import toast from 'react-hot-toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createPost, updatePost } from '../../api/posts'
import { createReminder as apiCreateReminder } from '../../api/reminders'
import { getChannels } from '../../api/channels'
import { useEditorStore } from '../../store/editorStore'
import type { PostCreate, PostStatus } from '../../types'
import NetworkSelector from './NetworkSelector'
import ChannelSelector from './ChannelSelector'
import DualTextEditor from './DualTextEditor'
import MediaUploader from './MediaUploader'
import DateTimePicker from './DateTimePicker'
import PostPreview from './PostPreview'
import PollEditor from './PollEditor'
import ReminderEditor from './ReminderEditor'
import styles from './PostEditor.module.css'

interface Props {
  editPostId?: number
}

// собираем URL календаря с week-параметром, соответствующим дате поста
function buildCalendarUrl(scheduledAt?: string | null): string {
  if (!scheduledAt) return '/'
  try {
    const d = typeof scheduledAt === 'string' ? parseISO(scheduledAt) : scheduledAt
    const weekStart = startOfWeek(d, { weekStartsOn: 1 })
    return `/?week=${format(weekStart, 'yyyy-MM-dd')}`
  } catch {
    return '/'
  }
}

export default function PostEditor({ editPostId }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const store = useEditorStore()
  const { data: allChannels = [] } = useQuery({ queryKey: ['channels'], queryFn: () => getChannels() })

  // проверка: опрос + VK канал требует обязательное описание (text_plain)
  function validatePollVk(): string | null {
    if (!store.pollDraft) return null
    const selectedVk = allChannels.some(c =>
      store.selectedChannels.includes(c.id) && c.platform === 'vk'
    )
    if (!selectedVk) return null
    if (!store.textPlain || !store.textPlain.trim()) {
      return 'ВКонтакте не публикует опрос без описания. Заполни поле "Текст для ВК / Instagram / Max" или убери ВК канал.'
    }
    return null
  }

  // TG caption на фото/медиа ограничен 1024 символами. Если больше - TG вернёт ошибку.
  // Считаем длину без HTML-тегов - именно её TG применяет к caption.
  function validateTgCaption(): string | null {
    const hasTg = allChannels.some(c =>
      store.selectedChannels.includes(c.id) && c.platform === 'tg'
    )
    if (!hasTg) return null
    if (!store.mediaPaths || store.mediaPaths.length === 0) return null
    const raw = (store.textTgHtml || '').replace(/<[^>]+>/g, '')
    if (raw.length <= 1024) return null
    return `Для TG подпись к фото/медиа не может быть длиннее 1024 символов (сейчас ${raw.length}). Убери медиа, укороти текст или сними TG-канал.`
  }

  function validateAll(): string | null {
    return validatePollVk() || validateTgCaption()
  }

  const mutation = useMutation({
    mutationFn: async (status: PostStatus) => {
      const data: PostCreate = {
        title: store.title || undefined,
        text_tg_html: store.textTgHtml || undefined,
        text_plain: store.textPlain || undefined,
        media_paths: store.mediaPaths,
        poll_json: store.pollDraft ?? undefined,
        status,
        scheduled_at: store.scheduledAt ? `${store.scheduledAt}:00` : undefined,
        targets: store.selectedChannels.map(id => ({ channel_id: id })),
      }

      let post
      if (editPostId) {
        post = await updatePost(editPostId, data)
      } else {
        post = await createPost(data)
      }

      // save reminders
      for (const r of store.reminders) {
        if (!r.message) continue
        await apiCreateReminder({
          post_id: post.id,
          message: r.message,
          send_at: r.send_at ? new Date(r.send_at).toISOString() : null,
        })
      }

      return post
    },
    onSuccess: (post, status) => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
      qc.invalidateQueries({ queryKey: ['posts'] })
      store.reset()
      toast.success(status === 'draft' ? 'Черновик сохранён' : 'Пост запланирован!')
      navigate(buildCalendarUrl(post.scheduled_at))
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка'),
  })

  async function handlePublishNow() {
    try {
      const { publishPost } = await import('../../api/posts')
      let postId = editPostId
      // для нового поста сначала сохраняем как draft, потом публикуем
      if (!postId) {
        // ставим scheduled_at = сейчас, чтобы пост был виден в календаре
        const now = new Date()
        const pad = (n: number) => String(n).padStart(2, '0')
        const localNow = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
        const data: PostCreate = {
          text_tg_html: store.textTgHtml || undefined,
          text_plain: store.textPlain || undefined,
          media_paths: store.mediaPaths,
          poll_json: store.pollDraft ?? undefined,
          status: 'draft',
          scheduled_at: store.scheduledAt ? `${store.scheduledAt}:00` : localNow,
          targets: store.selectedChannels.map(id => ({ channel_id: id })),
        }
        const created = await createPost(data)
        postId = created.id
        // сохраняем напоминания
        for (const r of store.reminders) {
          if (!r.message) continue
          await apiCreateReminder({
            post_id: postId,
            message: r.message,
            send_at: r.send_at ? new Date(r.send_at).toISOString() : null,
          })
        }
      }
      await publishPost(postId)
      qc.invalidateQueries({ queryKey: ['calendar'] })
      qc.invalidateQueries({ queryKey: ['posts'] })
      store.reset()
      toast.success('Публикуется...')
      navigate(buildCalendarUrl(store.scheduledAt))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Ошибка публикации')
    }
  }

  return (
    <div className={styles.layout}>
      <div className={styles.formScroll}>
        <div className={styles.form}>
          <NetworkSelector />
          <ChannelSelector />

          <div className={styles.divider} />

          <DualTextEditor />
          <MediaUploader />
          <PollEditor />

          <div className={styles.divider} />

          <DateTimePicker />
          <ReminderEditor />

          <div className={styles.divider} />

          <div className={styles.actions}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => mutation.mutate('draft')}
              disabled={mutation.isPending}
            >
              Сохранить черновик
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                const err = validateAll()
                if (err) { toast.error(err); return }
                mutation.mutate('scheduled')
              }}
              disabled={mutation.isPending || !store.scheduledAt}
            >
              Запланировать
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                const err = validateAll()
                if (err) { toast.error(err); return }
                handlePublishNow()
              }}
              disabled={mutation.isPending || store.selectedChannels.length === 0}
            >
              Опубликовать сейчас
            </button>
          </div>
        </div>
      </div>

      <div className={styles.previewScroll}>
        <div className={styles.preview}>
          <div className={styles.previewTitle}>Предпросмотр</div>
          <PostPreview />
        </div>
      </div>
    </div>
  )
}
