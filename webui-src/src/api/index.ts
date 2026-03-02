import axios from 'axios'
import type { AxiosInstance, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios'

const DB_NOT_CONFIGURED_MSG = '数据库未配置'

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── 请求拦截器：注入 Bearer token ────────────────────────────────────────────
http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('mc_access_token')
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// ── 401 刷新队列（防止并发 401 多次刷新）────────────────────────────────────
let _isRefreshing = false
let _refreshWaiters: Array<(token: string | null) => void> = []

function _subscribeRefresh(callback: (token: string | null) => void) {
  _refreshWaiters.push(callback)
}

function _resolveWaiters(token: string | null) {
  _refreshWaiters.forEach((cb) => cb(token))
  _refreshWaiters = []
}

// Response interceptor — unwrap { code, message, data } + 401 自动刷新
http.interceptors.response.use(
  (response: AxiosResponse) => {
    const body = response.data
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return Promise.reject(new Error(body.message || 'API Error'))
    }
    return response
  },
  async (error: AxiosError<{ detail?: string }>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // ── 401 处理：尝试用 refresh_token 换取新 token ─────────────────────────
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 如果来自 /auth/* 本身的 401，不要重试（避免死循环）
      const url = originalRequest.url ?? ''
      if (url.startsWith('/auth/') || url.includes('/api/auth/')) {
        return Promise.reject(error)
      }

      originalRequest._retry = true

      if (_isRefreshing) {
        // 当前已在刷新中，排队等待
        return new Promise((resolve, reject) => {
          _subscribeRefresh((newToken) => {
            if (newToken) {
              originalRequest.headers['Authorization'] = `Bearer ${newToken}`
              resolve(http(originalRequest))
            } else {
              reject(error)
            }
          })
        })
      }

      _isRefreshing = true
      const refreshToken = localStorage.getItem('mc_refresh_token')

      if (!refreshToken) {
        // 没有 refresh token → 直接跳转登录
        _isRefreshing = false
        _resolveWaiters(null)
        _redirectToLogin()
        return Promise.reject(error)
      }

      try {
        const resp = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
        const { access_token, refresh_token: newRt } = resp.data
        localStorage.setItem('mc_access_token', access_token)
        if (newRt) localStorage.setItem('mc_refresh_token', newRt)

        originalRequest.headers['Authorization'] = `Bearer ${access_token}`
        _resolveWaiters(access_token)
        return http(originalRequest)
      } catch {
        localStorage.removeItem('mc_access_token')
        localStorage.removeItem('mc_refresh_token')
        _resolveWaiters(null)
        _redirectToLogin()
        return Promise.reject(error)
      } finally {
        _isRefreshing = false
      }
    }

    // ── 400 DB 未配置错误 ────────────────────────────────────────────────────
    if (error.response?.status === 400) {
      const detail = error.response.data?.detail || ''
      if (detail.includes(DB_NOT_CONFIGURED_MSG)) {
        const err = new Error('当前存储模式为 CSV/JSON，此功能需要数据库。请前往「配置管理」切换到 DB 模式。') as Error & { isDbNotConfigured: boolean }
        err.isDbNotConfigured = true
        return Promise.reject(err)
      }
    }

    return Promise.reject(error)
  },
)

function _redirectToLogin() {
  // 避免在登录页重复跳转
  if (!window.location.pathname.endsWith('/login')) {
    window.location.href = '/login'
  }
}

/** Check if an error is the "DB not configured" case */
export function isDbError(err: unknown): boolean {
  return typeof err === 'object' && err !== null && 'isDbNotConfigured' in err && (err as any).isDbNotConfigured === true
}

/**
 * 统一解包后端响应数据。
 * - 标准: { code, message, data }
 * - 旧版: 直接返回业务对象
 */
export function unwrapApiData<T = any>(body: any): T {
  if (body && typeof body === 'object' && 'data' in body) {
    return body.data as T
  }
  return body as T
}

export default http
