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

  // глобальный слушатель горячих клавиш, активный пока textarea в фокусе.
  // Используем e.code (физическая клавиша), чтобы Ctrl+B работал и на русской раскладке.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (document.activeElement !== textareaRef.current) return
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return
      const codeMap: Record<string, string> = {
        KeyB: 'bold',
        KeyI: 'italic',
        KeyU: 'underline',
        KeyS: 'strike',
      }
      const fmt = codeMap[e.code]
      if (!fmt) return
      e.preventDefault()
      e.stopPropagation()
      applyFormat(fmt)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [applyFormat])

  function insertEmoji(emoji: string) {
    const el = textareaRef.current
    if (!el) return
    const pos = el.selectionStart
    const end = el.selectionEnd
    const newText = textTg.slice(0, pos) + emoji + textTg.slice(end)
    // удалили (end-pos) символов с позиции pos, вставили emoji.length
    const shifted = shiftRangesPrecise(textTgRanges, pos, end - pos, emoji.length, newText.length)
    setTextTg(newText)
    if (shifted !== textTgRanges) setTextTgRanges(shifted)
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
            // точный diff через общий префикс/суффикс
            const { start, removed, inserted } = diffTexts(oldText, newText)
            const shifted = shiftRangesPrecise(textTgRanges, start, removed, inserted, newText.length)
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
            height={480}
            width={420}
            searchPlaceHolder="Поиск эмодзи..."
            previewConfig={{ showPreview: false }}
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

// Находим точный diff между старым и новым текстом через общий префикс и суффикс.
// Возвращает: позиция изменения, сколько удалено, сколько вставлено.
function diffTexts(oldText: string, newText: string): { start: number; removed: number; inserted: number } {
  if (oldText === newText) return { start: 0, removed: 0, inserted: 0 }
  // общий префикс
  let start = 0
  const maxStart = Math.min(oldText.length, newText.length)
  while (start < maxStart && oldText[start] === newText[start]) start++
  // общий суффикс (но не залезаем в уже сматченный префикс)
  let oldEnd = oldText.length
  let newEnd = newText.length
  while (oldEnd > start && newEnd > start && oldText[oldEnd - 1] === newText[newEnd - 1]) {
    oldEnd--
    newEnd--
  }
  return { start, removed: oldEnd - start, inserted: newEnd - start }
}

// Точный сдвиг ranges при замене [start, start+removed) на текст длины inserted.
// Каждая граница r.start/r.end независимо отображается через mapPoint.
function shiftRangesPrecise(
  ranges: FormatRange[],
  changeStart: number,
  removed: number,
  inserted: number,
  newLen: number,
): FormatRange[] {
  if (removed === 0 && inserted === 0) return ranges
  const changeEnd = changeStart + removed
  const delta = inserted - removed

  function mapPoint(p: number, isEnd: boolean): number {
    // граница до зоны изменения - не сдвигается
    if (p <= changeStart) return p
    // граница в зоне удаления:
    //   - для start: схлопывается к началу изменения (т.к. содержимое удалено)
    //   - для end:   тоже схлопывается, чтобы не "захватить" вставленное
    if (p <= changeEnd) return changeStart
    // граница после зоны изменения - сдвигается на delta
    return p + delta
  }

  const result: FormatRange[] = []
  for (const r of ranges) {
    const start = mapPoint(r.start, false)
    const end = mapPoint(r.end, true)
    const clampedStart = Math.max(0, Math.min(start, newLen))
    const clampedEnd = Math.max(0, Math.min(end, newLen))
    if (clampedEnd > clampedStart) {
      result.push({ ...r, start: clampedStart, end: clampedEnd })
    }
  }
  return result
}
