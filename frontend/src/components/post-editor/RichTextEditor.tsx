import { useRef, useState, useCallback, useEffect } from 'react'
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

    // для link не делаем тоггл - просто заменяем
    if (type === 'link') {
      const filtered = textTgRanges.filter(r => !(r.type === type && r.start < end && r.end > start))
      const newRange: FormatRange = { start, end, type: type as FormatRange['type'], url }
      setTextTgRanges([...filtered, newRange].sort((a, b) => a.start - b.start))
      return
    }

    // тоггл: если выделение полностью покрыто range того же типа - снимаем форматирование
    const fullyCovered = textTgRanges.some(r => r.type === type && r.start <= start && r.end >= end)
    if (fullyCovered) {
      const result: FormatRange[] = []
      for (const r of textTgRanges) {
        if (r.type !== type || r.end <= start || r.start >= end) {
          result.push(r)
          continue
        }
        // вырезаем кусок [start, end] из range r
        if (r.start < start) result.push({ ...r, start: r.start, end: start })
        if (r.end > end) result.push({ ...r, start: end, end: r.end })
      }
      setTextTgRanges(result.sort((a, b) => a.start - b.start))
      return
    }

    // иначе - добавляем (и сливаем с пересекающимися того же типа в один большой range)
    const overlapping = textTgRanges.filter(r => r.type === type && r.start <= end && r.end >= start)
    const other = textTgRanges.filter(r => !(r.type === type && r.start <= end && r.end >= start))
    const mergedStart = Math.min(start, ...overlapping.map(r => r.start))
    const mergedEnd = Math.max(end, ...overlapping.map(r => r.end))
    const newRange: FormatRange = { start: mergedStart, end: mergedEnd, type: type as FormatRange['type'] }
    setTextTgRanges([...other, newRange].sort((a, b) => a.start - b.start))
  }, [textTg, textTgRanges, setTextTgRanges])

  // глобальный слушатель горячих клавиш, активный пока textarea в фокусе
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const focused = document.activeElement === textareaRef.current
      const isCtrl = e.ctrlKey || e.metaKey
      if (!isCtrl || e.altKey || e.shiftKey) return
      const key = e.key.toLowerCase()
      const map: Record<string, string> = { b: 'bold', i: 'italic', u: 'underline', s: 'strike' }
      if (!map[key]) return
      console.log('[RichTextEditor] hotkey', { key, focused, sel: textareaRef.current ? [textareaRef.current.selectionStart, textareaRef.current.selectionEnd] : null })
      if (!focused) return
      e.preventDefault()
      e.stopPropagation()
      applyFormat(map[key])
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [applyFormat])

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
            const newText = e.target.value
            const oldText = textTg
            // вычисляем точку начала изменения и дельту длины, сдвигаем ranges
            const cursorPos = e.target.selectionStart
            const delta = newText.length - oldText.length
            const changeStart = cursorPos - Math.max(delta, 0)
            const shifted = shiftRanges(textTgRanges, changeStart, delta, newText.length)
            setTextTg(newText)
            if (shifted !== textTgRanges) setTextTgRanges(shifted)
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
      case 'underline': result += `<u>${chunk}</u>`; break
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

// сдвигаем ranges при изменении текста: всё что после changeStart смещается на delta
function shiftRanges(ranges: FormatRange[], changeStart: number, delta: number, newLen: number): FormatRange[] {
  if (delta === 0) return ranges
  const result: FormatRange[] = []
  for (const r of ranges) {
    let { start, end } = r
    if (end <= changeStart) {
      // изменение полностью после range - не трогаем
      result.push(r)
      continue
    }
    if (start >= changeStart - delta && delta < 0) {
      // удалили кусок, начинающийся ДО range - сдвигаем start/end назад
      start = Math.max(changeStart, start + delta)
      end = Math.max(changeStart, end + delta)
    } else if (start >= changeStart) {
      // изменение полностью до range - сдвигаем обе границы
      start += delta
      end += delta
    } else {
      // изменение внутри range - расширяем/сжимаем end
      end += delta
    }
    start = Math.max(0, Math.min(start, newLen))
    end = Math.max(0, Math.min(end, newLen))
    if (end > start) result.push({ ...r, start, end })
  }
  return result
}
