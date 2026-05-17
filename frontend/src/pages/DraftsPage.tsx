import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import toast from 'react-hot-toast'
import { getPosts, deletePost, publishPost } from '../api/posts'
import StatusBadge from '../components/shared/StatusBadge'
import styles from './DraftsPage.module.css'

export default function DraftsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: drafts = [] } = useQuery({
    queryKey: ['posts', 'draft'],
    queryFn: () => getPosts({ status: 'draft' }),
  })

  const { data: scheduled = [] } = useQuery({
    queryKey: ['posts', 'scheduled'],
    queryFn: () => getPosts({ status: 'scheduled' }),
  })

  const deleteMutation = useMutation({
    mutationFn: deletePost,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['posts'] }); toast.success('Удалено') },
  })

  const posts = [...scheduled, ...drafts]

  return (
    <div className={styles.page}>
      <h2 className={styles.title}>Черновики и запланированные</h2>
      {posts.length === 0 && <p className={styles.empty}>Нет постов</p>}
      <div className={styles.list}>
        {posts.map(p => (
          <div key={p.id} className={styles.item}>
            <div className={styles.itemMain}>
              <div className={styles.itemTop}>
                <StatusBadge status={p.status} />
                {p.scheduled_at && (
                  <span className={styles.time}>
                    {format(parseISO(p.scheduled_at), 'dd.MM.yyyy HH:mm')}
                  </span>
                )}
                <div className={styles.platforms}>
                  {p.platforms.map(pl => (
                    <span key={pl} className={`platform-chip chip-${pl}`}>{pl.toUpperCase()}</span>
                  ))}
                </div>
              </div>
              {p.title && <div className={styles.itemTitle}>{p.title}</div>}
              {p.preview_text && <p className={styles.preview}>{p.preview_text}</p>}
            </div>
            <div className={styles.itemActions}>
              <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/posts/${p.id}/edit`)}>
                Редактировать
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => deleteMutation.mutate(p.id)}>
                Удалить
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
