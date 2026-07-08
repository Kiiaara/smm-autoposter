import client from './client'

export interface ChannelSummary {
  channel_id: number
  name: string
  platform: string
  subscribers: number
  avg_views: number
  avg_likes: number
  posts_count: number
}

export interface ServicePostsSummary {
  channel_id: number
  name: string
  platform: string
  posts_count: number
  avg_views: number
  avg_likes: number
  avg_comments: number
  avg_reposts: number
  total_views: number
  total_likes: number
  total_reposts: number
  total_comments: number
}

export interface Overview {
  total_posts: number
  total_views: number
  total_likes: number
  total_comments: number
  channels: ChannelSummary[]
  service_posts: ServicePostsSummary[]
}

export interface TopPost {
  post_id: number
  title?: string
  preview?: string
  platform: string
  channel_name: string
  published_at: string
  url?: string
  views: number
  likes: number
  reposts: number
  comments: number
}

export interface SubscriberPoint { date: string; subscribers: number }
export interface SubscriberSeries {
  channel_id: number
  name: string
  platform: string
  points: SubscriberPoint[]
}

export interface BestTimeCell {
  day_of_week: number
  hour: number
  avg_views: number
  posts: number
}

export const getOverview = (period_days = 30) =>
  client.get<Overview>('/stats/overview', { params: { period_days } }).then(r => r.data)

export const getTopPosts = (params: { period_days?: number; sort_by?: string; limit?: number; platform?: string; channel_id?: number } = {}) =>
  client.get<TopPost[]>('/stats/posts', { params }).then(r => r.data)

export const getSubscribers = (period_days = 30) =>
  client.get<SubscriberSeries[]>('/stats/subscribers', { params: { period_days } }).then(r => r.data)

export const getBestTime = (period_days = 60) =>
  client.get<BestTimeCell[]>('/stats/best-time', { params: { period_days } }).then(r => r.data)

interface CollectParams {
  period_days?: number
  since_date?: string  // YYYY-MM-DD
  until_date?: string  // YYYY-MM-DD
}

export const collectTgNow = (params: CollectParams = { period_days: 30 }) =>
  client.post<{ ok: boolean; channels: any[] }>('/stats/tg/collect-now', null, {
    params,
    timeout: 10 * 60 * 1000, // 10 минут - Telethon может идти долго через VPN
  }).then(r => r.data)

export const collectTtNow = (params: CollectParams = { period_days: 30 }) =>
  client.post<{ ok: boolean; channels: any[] }>('/stats/tt/collect-now', null, {
    params,
    timeout: 10 * 60 * 1000,
  }).then(r => r.data)

export interface ChannelTotal {
  channel_id: number
  name: string
  platform: string
  posts_count: number
  total_views: number
  total_likes: number
  total_reposts: number
  total_comments: number
}

export const getChannelTotals = (params: { since_date?: string; until_date?: string; period_days?: number }) =>
  client.get<ChannelTotal[]>('/stats/channel-totals', { params }).then(r => r.data)
