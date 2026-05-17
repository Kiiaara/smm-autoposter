import styles from './ConfirmModal.module.css'

interface Props {
  message: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmModal({ message, onConfirm, onCancel }: Props) {
  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <p>{message}</p>
        <div className={styles.actions}>
          <button className="btn btn-secondary" onClick={onCancel}>Отмена</button>
          <button className="btn btn-danger" onClick={onConfirm}>Удалить</button>
        </div>
      </div>
    </div>
  )
}
