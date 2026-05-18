import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

// при 401 редиректим на /login (кроме самих auth-эндпоинтов)
client.interceptors.response.use(
  r => r,
  err => {
    if (err?.response?.status === 401) {
      const url = err.config?.url || ''
      if (!url.startsWith('/auth/')) {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

export default client
