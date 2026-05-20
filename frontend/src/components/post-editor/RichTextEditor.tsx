import { useEffect, useRef, useState } from 'react'
import EmojiPickerReact from 'emoji-picker-react'
import { useEditorStore } from '../../store/editorStore'
import styles from './RichTextEditor.module.css'

export default function RichTextEditor() {
  const { textTgHtml, setTextTgHtml } = useEditorStore()
  const editorRef = useRef<HTMLDivElement>(null)
  const [showEmoji, setShowEmoji] = useState(false)
  // Запоминаем последнюю позицию курсора в редакторе (для вставки эмодзи после блюра)
  const savedRange = useRef<Range | null>(null)
  // Инициализация: загружаем HTML в DOM только один раз (или когда внешний значение поменялось извне)
  const lastSyncedHtml = useRef<string>('')

  useEffect(() => {
    const el = editorRef.current
    if (!el) return
    // если store изменился извне (например при загрузке поста для редактирования) - обновляем DOM
    if (textTgHtml !== lastSyncedHtml.current && textTgHtml !== el.innerHTML) {
      el.innerHTML = textTgHtml || ''
      lastSyncedHtml.current = textTgHtml || ''
    }
  }, [textTgHtml])

  function saveSelection() {
    const sel = window.getSelection()
    if (sel && sel.rangeCount > 0 && editorRef.current?.contains(sel.anchorNode)) {
      savedRange.current = sel.getRangeAt(0).cloneRange()
    }
  }

  function restoreSelection() {
    const range = savedRange.current
    if (!range) {
      // ставим курсор в конец редактора
      editorRef.current?.focus()
      const sel = window.getSelection()
      if (sel && editorRef.current) {
        const r = document.createRange()
        r.selectNodeContents(editorRef.current)
        r.collapse(false)
        sel.removeAllRanges()
        sel.addRange(r)
      }
      return
    }
    editorRef.current?.focus()
    const sel = window.getSelection()
    if (sel) {
      sel.removeAllRanges()
      sel.addRange(range)
    }
  }

  function syncToStore() {
    const el = editorRef.current
    if (!el) return
    const html = el.innerHTML
    lastSyncedHtml.current = html
    setTextTgHtml(html)
  }

  function exec(command: string, value?: string) {
    restoreSelection()
    document.execCommand(command, false, value)
    saveSelection()
    syncToStore()
  }

  function wrapSpoiler() {
    restoreSelection()
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0) return
    const range = sel.getRangeAt(0)
    if (range.collapsed) return
    const text = range.toString()
    const span = document.createElement('tg-spoiler')
    span.textContent = text
    range.deleteContents()
    range.insertNode(span)
    // ставим курсор после спойлера
    range.setStartAfter(span)
    range.collapse(true)
    sel.removeAllRanges()
    sel.addRange(range)
    saveSelection()
    syncToStore()
  }

  function addLink() {
    restoreSelection()
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
      alert('Сначала выдели текст, потом жми "Ссылка"')
      return
    }
    const url = prompt('URL ссылки:')
    if (!url) return
    exec('createLink', url)
  }

  function insertEmoji(emoji: string) {
    restoreSelection()
    document.execCommand('insertText', false, emoji)
    saveSelection()
    syncToStore()
    setShowEmoji(false)
  }

  function clearFormat() {
    restoreSelection()
    document.execCommand('removeFormat')
    document.execCommand('unlink')
    saveSelection()
    syncToStore()
  }

  // Ctrl+B / I / U / S через физические коды клавиш (работает на любой раскладке)
  function handleKeyDown(e: React.KeyboardEvent) {
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return
    const map: Record<string, string> = {
      KeyB: 'bold',
      KeyI: 'italic',
      KeyU: 'underline',
      KeyS: 'strikeThrough',
    }
    const cmd = map[e.code]
    if (!cmd) return
    e.preventDefault()
    document.execCommand(cmd)
    saveSelection()
    syncToStore()
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.toolbar} onMouseDown={e => e.preventDefault()}>
        <button type="button" className={styles.toolBtn} onClick={() => exec('bold')} title="Жирный (Ctrl+B)" style={{ fontWeight: 700 }}>B</button>
        <button type="button" className={styles.toolBtn} onClick={() => exec('italic')} title="Курсив (Ctrl+I)" style={{ fontStyle: 'italic' }}>I</button>
        <button type="button" className={styles.toolBtn} onClick={() => exec('underline')} title="Подчёркнутый (Ctrl+U)" style={{ textDecoration: 'underline' }}>U</button>
        <button type="button" className={styles.toolBtn} onClick={() => exec('strikeThrough')} title="Зачёркнутый (Ctrl+S)" style={{ textDecoration: 'line-through' }}>S</button>
        <button type="button" className={styles.toolBtn} onClick={wrapSpoiler} title="Спойлер">||</button>
        <button type="button" className={styles.toolBtn} onClick={addLink} title="Ссылка">🔗</button>
        <button type="button" className={styles.toolBtn} onClick={() => setShowEmoji(v => !v)} title="Эмодзи">😊</button>
        <button type="button" className={styles.toolBtn} onClick={clearFormat} title="Убрать форматирование" style={{ marginLeft: 'auto' }}>⌫</button>
      </div>
      <div className={styles.editorArea}>
        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          className={styles.editor}
          onInput={syncToStore}
          onBlur={saveSelection}
          onKeyUp={saveSelection}
          onMouseUp={saveSelection}
          onKeyDown={handleKeyDown}
          data-placeholder="Текст для Telegram..."
        />
        {showEmoji && (
          <div className={styles.emojiWrapper}>
            <EmojiPickerReact
              onEmojiClick={e => insertEmoji(e.emoji)}
              theme={'dark' as any}
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
