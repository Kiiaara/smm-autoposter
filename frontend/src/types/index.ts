export type Platform = 'tg' | 'vk' | 'ig' | 'max'
export type PostStatus = 'draft' | 'scheduled' | 'published' | 'failed'
export type PostTargetStatus = 'pending' | 'published' | 'failed'

export interface FormatRange {
  start: number
  end: number
  type: 'bold' | 'italic' | 'underline' | 'strike' | 'code' | 'spoiler' | 'link'
  url?: string
}

export interface PollData {
  question: string
  options: string[]
  is_anonymous: boolean
  allows_multiple_answers: boolean
  tg_no_text: boolean
}

export interface PostTarget {
  id: number
  channel_id: number
  status: PostTargetStatus
  published_at?: string
  error?: string
}

export interface Post {
  id: number
  title?: string
  text_tg_html?: string
  text_tg?: string
  text_tg_ranges: FormatRange[]
  text_plain?: string
  media_paths: string[]
  poll_json?: PollData
  status: PostStatus
  scheduled_at?: string
  created_at: string
  updated_at: string
  targets: PostTarget[]
}

export interface PostListItem {
  id: number
  title?: string
  status: PostStatus
  scheduled_at?: string
  created_at: string
  platforms: Platform[]
  preview_text?: string
}

export interface PostCreate {
  title?: string
  text_tg_html?: string
  text_tg?: string  // legacy
  text_tg_ranges?: FormatRange[]  // legacy
  text_plain?: string
  media_paths?: string[]
  poll_json?: PollData
  status: PostStatus
  scheduled_at?: string
  targets: { channel_id: number }[]
}

export interface Channel {
  id: number
  name: string
  platform: Platform
  is_active: boolean
  config_json: Record<string, string>
}

export interface ChannelCreate {
  name: string
  platform: Platform
  config_json: Record<string, string>
}

export interface ScheduleSlot {
  id: number
  day_of_week: number
  slot_time: string
}

export interface AvailableSlot {
  slot_time: string
  is_free: boolean
}

export interface Reminder {
  id: number
  post_id: number
  message: string
  send_at: string | null
  sent: boolean
  sent_at?: string
}

export interface CalendarTargetStatus {
  channel_name: string
  platform: Platform
  status: PostTargetStatus
  error?: string
  url?: string
}

export interface CalendarPost {
  id: number
  title?: string
  status: PostStatus
  scheduled_at: string
  platforms: Platform[]
  preview_text?: string
  has_poll: boolean
  targets: CalendarTargetStatus[]
}

export interface CalendarSlot {
  slot_time: string
  is_free: boolean
}

export interface CalendarDay {
  date: string
  slots: CalendarSlot[]
  posts: CalendarPost[]
}

export interface CalendarResponse {
  week_start: string
  days: CalendarDay[]
}
