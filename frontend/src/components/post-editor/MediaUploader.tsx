import { useRef, useState } from 'react'
import { uploadFiles } from '../../api/posts'
import { useEditorStore } from '../../store/editorStore'
import styles from './MediaUploader.module.css'

export default function MediaUploader() {
  const { mediaPaths, setMediaPaths } = useEditorStore()
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    const arr = Array.from(files).slice(0, 10 - mediaPaths.length)
    if (arr.length === 0) return
    setUploading(true)
    try {
      const paths = await uploadFiles(arr)
      setMediaPaths([...mediaPaths, ...paths])
    } finally {
      setUploading(false)
    }
  }

  function removeMedia(path: string) {
    setMediaPaths(mediaPaths.filter(p => p !== path))
  }

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.dropzone}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files) }}
      >
        {uploading ? 'Загружаю...' : '+ Добавить фото/видео (до 10)'}
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/*,video/mp4"
        style={{ display: 'none' }}
        onChange={e => handleFiles(e.target.files)}
      />
      {mediaPaths.length > 0 && (
        <div className={styles.previews}>
          {mediaPaths.map(p => (
            <div key={p} className={styles.thumb}>
              <img src={`/${p}`} alt="" />
              <button type="button" className={styles.remove} onClick={() => removeMedia(p)}>x</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
