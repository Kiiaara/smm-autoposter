import client from './client'
import type { Post, PostCreate, PostListItem } from '../types'

export const getPosts = (params?: Record<string, string>) =>
  client.get<PostListItem[]>('/posts', { params }).then(r => r.data)

export const getPost = (id: number) =>
  client.get<Post>(`/posts/${id}`).then(r => r.data)

export const createPost = (data: PostCreate) =>
  client.post<Post>('/posts', data).then(r => r.data)

export const updatePost = (id: number, data: Partial<PostCreate>) =>
  client.patch<Post>(`/posts/${id}`, data).then(r => r.data)

export const deletePost = (id: number) =>
  client.delete(`/posts/${id}`).then(r => r.data)

export const publishPost = (id: number) =>
  client.post(`/posts/${id}/publish`).then(r => r.data)

export const uploadFiles = (files: File[]) => {
  const fd = new FormData()
  files.forEach(f => fd.append('files', f))
  return client.post<{ paths: string[] }>('/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data.paths)
}
