import { useRef, useState } from 'react'
import EmojiPickerReact from 'emoji-picker-react'
import { useEditorStore } from '../../store/editorStore'
import styles from './PlainTextEditor.module.css'

export default function PlainTextEditor() {
  const { textTgHtml, textPlain, setTextPlain } = useEditorStore()
  const [showEmoji, setShowEmoji] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function copyFromTg() {
    // конвертируем HTML в plain text: <br>/<p>/<div> → \n, ссылки → "текст (url)", остальные теги убираем
    let s = textTgHtml || ''
    s = s.replace(/<br\s*\/?>/gi, '\n')
    s = s.replace(/<\/(p|div)>/gi, '\n')
    s = s.replace(/<(p|div)[^>]*>/gi, '')
    s = s.replace(/<a[^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/gi, (_, href, text) => {
      const t = text.replace(/<[^>]+>/g, '')
      return href && href !== t ? `${t} (${href})` : t
    })
    s = s.replace(/<[^>]+>/g, '')
    s = s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    setTextPlain(s.trim())
  }

  function attachVkArticle() {
    const url = prompt(
      'Вставь URL статьи VK\n\n' +
      'Чтобы создать: открой свою группу VK → "+ Запись" → справа выбери "Статья" → напиши и опубликуй.\n' +
      'Потом скопируй URL вида https://vk.com/@group_name-slug'
    )
    if (!url) return
    const trimmed = url.trim()
    if (!trimmed.includes('vk.com/@')) {
      alert('Это не похоже на URL статьи VK. Должен быть вида https://vk.com/@.../...')
      return
    }
    // добавляем URL в конец текста (с переводом строки если текст не пустой)
    const separator = textPlain && !textPlain.endsWith('\n') ? '\n\n' : ''
    setTextPlain(textPlain + separator + trimmed)
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
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={attachVkArticle}
          title="Прикрепить статью VK (создаётся в браузере VK, сюда вставляем URL)"
        >
          + Статья VK
        </button>
        {textTgHtml && (
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
              height={480}
              width={420}
              searchPlaceHolder="Поиск эмодзи..."
              previewConfig={{ showPreview: false }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
