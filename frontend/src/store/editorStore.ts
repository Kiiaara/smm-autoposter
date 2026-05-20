import { create } from 'zustand'
import type { Platform, FormatRange, PollData } from '../types'

interface ReminderDraft {
  message: string
  send_at: string | null  // null = после публикации (через 2 мин)
}

interface EditorState {
  title: string
  textTgHtml: string  // новый формат - HTML строка
  textTg: string  // legacy
  textTgRanges: FormatRange[]  // legacy
  textPlain: string
  mediaPaths: string[]
  selectedNetworks: Platform[]
  selectedChannels: number[]
  scheduledAt: string
  pollDraft: PollData | null
  reminders: ReminderDraft[]

  setTitle: (v: string) => void
  setTextTgHtml: (v: string) => void
  setTextTg: (v: string) => void
  setTextTgRanges: (v: FormatRange[]) => void
  setTextPlain: (v: string) => void
  setMediaPaths: (v: string[]) => void
  toggleNetwork: (p: Platform) => void
  setSelectedChannels: (ids: number[]) => void
  setScheduledAt: (v: string) => void
  setPollDraft: (v: PollData | null) => void
  addReminder: (r: ReminderDraft) => void
  removeReminder: (idx: number) => void
  reset: () => void
}

const defaults = {
  title: '',
  textTgHtml: '',
  textTg: '',
  textTgRanges: [] as FormatRange[],
  textPlain: '',
  mediaPaths: [] as string[],
  selectedNetworks: [] as Platform[],
  selectedChannels: [] as number[],
  scheduledAt: '',
  pollDraft: null as PollData | null,
  reminders: [] as ReminderDraft[],
}

export const useEditorStore = create<EditorState>(set => ({
  ...defaults,
  setTitle: (v) => set({ title: v }),
  setTextTgHtml: (v) => set({ textTgHtml: v }),
  setTextTg: (v) => set({ textTg: v }),
  setTextTgRanges: (v) => set({ textTgRanges: v }),
  setTextPlain: (v) => set({ textPlain: v }),
  setMediaPaths: (v) => set({ mediaPaths: v }),
  toggleNetwork: (p) => set(s => ({
    selectedNetworks: s.selectedNetworks.includes(p)
      ? s.selectedNetworks.filter(n => n !== p)
      : [...s.selectedNetworks, p],
  })),
  setSelectedChannels: (ids) => set({ selectedChannels: ids }),
  setScheduledAt: (v) => set({ scheduledAt: v }),
  setPollDraft: (v) => set({ pollDraft: v }),
  addReminder: (r) => set(s => ({ reminders: [...s.reminders, r] })),
  removeReminder: (idx) => set(s => ({ reminders: s.reminders.filter((_, i) => i !== idx) })),
  reset: () => set(defaults),
}))
