import type { PostStatus } from '../../types'

const LABELS: Record<PostStatus, string> = {
  draft: 'Черновик',
  scheduled: 'Запланирован',
  published: 'Опубликован',
  failed: 'Ошибка',
}

export default function StatusBadge({ status }: { status: PostStatus }) {
  return <span className={`badge badge-${status}`}>{LABELS[status]}</span>
}
