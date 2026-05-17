import { useState } from 'react'
import { useEditorStore } from '../../store/editorStore'
import type { PollData } from '../../types'
import styles from './PollEditor.module.css'

export default function PollEditor() {
  const { pollDraft, setPollDraft } = useEditorStore()
  const [open, setOpen] = useState(false)

  function initPoll() {
    setPollDraft({ question: '', options: ['', ''], is_anonymous: true, allows_multiple_answers: false, tg_no_text: true })
    // tg_no_text всегда true: в TG опрос идёт отдельным сообщением без текста
    setOpen(true)
  }

  function removePoll() {
    setPollDraft(null)
    setOpen(false)
  }

  function updatePoll(patch: Partial<PollData>) {
    if (!pollDraft) return
    setPollDraft({ ...pollDraft, ...patch })
  }

  function addOption() {
    if (!pollDraft || pollDraft.options.length >= 10) return
    updatePoll({ options: [...pollDraft.options, ''] })
  }

  function updateOption(i: number, val: string) {
    if (!pollDraft) return
    const opts = [...pollDraft.options]
    opts[i] = val
    updatePoll({ options: opts })
  }

  function removeOption(i: number) {
    if (!pollDraft || pollDraft.options.length <= 2) return
    updatePoll({ options: pollDraft.options.filter((_, idx) => idx !== i) })
  }

  if (!pollDraft) {
    return (
      <button type="button" className="btn btn-secondary btn-sm" onClick={initPoll}>
        + Добавить опрос
      </button>
    )
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span className={styles.title}>Опрос</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={removePoll}>Удалить опрос</button>
      </div>

      <input
        className="input"
        placeholder="Вопрос..."
        value={pollDraft.question}
        onChange={e => updatePoll({ question: e.target.value })}
      />

      <div className={styles.options}>
        {pollDraft.options.map((opt, i) => (
          <div key={i} className={styles.optionRow}>
            <input
              className="input"
              placeholder={`Вариант ${i + 1}`}
              value={opt}
              onChange={e => updateOption(i, e.target.value)}
            />
            {pollDraft.options.length > 2 && (
              <button type="button" className="btn btn-icon" onClick={() => removeOption(i)}>x</button>
            )}
          </div>
        ))}
        {pollDraft.options.length < 10 && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={addOption}>+ Вариант</button>
        )}
      </div>

      <div className={styles.checkboxes}>
        <label>
          <input type="checkbox" checked={pollDraft.is_anonymous} onChange={e => updatePoll({ is_anonymous: e.target.checked })} />
          Анонимный
        </label>
        <label>
          <input type="checkbox" checked={pollDraft.allows_multiple_answers} onChange={e => updatePoll({ allows_multiple_answers: e.target.checked })} />
          Несколько ответов
        </label>
      </div>

      <div className={styles.pollHint}>
        В Telegram опрос публикуется отдельным сообщением (без текста). Для ВКонтакте обязательно нужно описание - иначе опрос не уйдёт.
      </div>
    </div>
  )
}
