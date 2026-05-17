import { useRef, useState, useCallback } from 'react'
import EmojiPickerReact from 'emoji-picker-react'
import type { FormatRange } from '../../types'
import { useEditorStore } from '../../store/editorStore'
import FormatToolbar from './FormatToolbar'
import styles from './RichTextEditor.module.css'

export default function RichTextEditor() {
  const { textTg, textTgRanges, setTextTg, setTextTgRanges } = useEditorStore()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [showEmoji, setShowEmoji] = useState(false)

  const applyFormat = useCallback((type: string, url?: string) => {
    const el = textareaRef.current
    if (!el) return
    const { selectionStart: start, selectionEnd: end } = el
    if (start === end && type !== 'link') return

    const newRange: FormatRange = { start, end, type: type as FormatRange['type'] }
    if (url) newRange.url = url

    // remove overlapping ranges of same type, then add new one
    const merged = textTgRanges.filter(r => !(r.type === type && r.start < end && r.end > start))
    setTextTgRanges([...merged, newRange].sort((a, b) => a.start - b.start))
  }, [textTg, textTgRanges, setTextTgRanges])

  function insertEmoji(emoji: string) {
    const el = textareaRef.current
    if (!el) return
    const pos = el.selectionStart
    const newText = textTg.slice(0, pos) + emoji + textTg.slice(el.selectionEnd)
    setTextTg(newText)
    setShowEmoji(false)
    setTimeout(() => {
      el.focus()
      el.setSelectionRange(pos + emoji.length, pos + emoji.length)
    }, 0)
  }

  // visual highlights using a rendered overlay (simplified: just show plaintext with bold markers)
  const highlighted = buildHighlightedPreview(textTg, textTgRanges)

  return (
    <div className={styles.wrapper}>
      <FormatToolbar onFormat={applyFormat} onEmoji={() => setShowEmoji(v => !v)} />
      <div className={styles.editorArea}>
        <div className={styles.highlight} aria-hidden dangerouslySetInnerHTML={{ __html: highlighted + '<br>' }} />
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={textTg}
          onChange={e => {
            setTextTg(e.target.value)
            // shift ranges on text change would require complex logic; reset on major changes
          }}
          placeholder="Текст для Telegram (с форматированием)..."
          rows={8}
          spellCheck
        />
      </div>
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
  )
}

function buildHighlightedPreview(text: string, ranges: FormatRange[]): string {
  if (!ranges.length) return escapeHtml(text)

  const sorted = [...ranges].sort((a, b) => a.start - b.start)
  let result = ''
  let pos = 0

  for (const r of sorted) {
    if (r.start > pos) result += escapeHtml(text.slice(pos, r.start))
    const chunk = escapeHtml(text.slice(r.start, r.end))
    switch (r.type) {
      case 'bold': result += `<strong>${chunk}</strong>`; break
      case 'italic': result += `<em>${chunk}</em>`; break
      case 'strike': result += `<s>${chunk}</s>`; break
      case 'code': result += `<code>${chunk}</code>`; break
      case 'spoiler': result += `<span class="spoiler">${chunk}</span>`; break
      case 'link': result += `<a href="${r.url || '#'}" target="_blank">${chunk}</a>`; break
      default: result += chunk
    }
    pos = r.end
  }
  if (pos < text.length) result += escapeHtml(text.slice(pos))
  return result
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
}
