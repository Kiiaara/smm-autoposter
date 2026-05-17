import { useRef, useState } from 'react'
import EmojiPickerReact from 'emoji-picker-react'
import { useEditorStore } from '../../store/editorStore'
import styles from './PlainTextEditor.module.css'

export default function PlainTextEditor() {
  const { textTg, textPlain, setTextPlain } = useEditorStore()
  const [showEmoji, setShowEmoji] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function copyFromTg() {
    setTextPlain(textTg)
  }

  function insertEmoji(emoji: string) {
    const el = textareaRef.current
    if (!el) {
      setTextPlain(textPlain + emoji)
      setShowEmoji(false)
      return
    }
    const pos = el.selectionStart
    const newText = textPlain.slice(0, pos) + emoji + textPlain.slice(el.selectionEnd)
    setTextPlain(newText)
    setShowEmoji(false)
    setTimeout(() => {
      el.focus()
      el.setSelectionRange(pos + emoji.length, pos + emoji.length)
    }, 0)
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.toolbar}>
        <button type="button" className={styles.toolBtn} onClick={() => setShowEmoji(v => !v)} title="Эмодзи">
          😊
        </button>
        {textTg && (
          <button type="button" className="btn btn-secondary btn-sm" style={{ marginLeft: 'auto' }} onClick={copyFromTg}>
            Скопировать из TG
          </button>
        )}
      </div>
      <div className={styles.editorArea}>
        <textarea
          ref={textareaRef}
          className={`input ${styles.textarea}`}
          value={textPlain}
          onChange={e => setTextPlain(e.target.value)}
          placeholder="Текст для ВК / Instagram / Max..."
          rows={8}
          spellCheck
        />
        {showEmoji && (
          <div className={styles.emojiWrapper}>
            <EmojiPickerReact
              onEmojiClick={e => insertEmoji(e.emoji)}
              theme={"dark" as any}
              height={350}
              width="100%"
            />
          </div>
        )}
      </div>
    </div>
  )
}
