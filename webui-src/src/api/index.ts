import axios from 'axios'
import type { AxiosInstance, AxiosResponse, AxiosError } from 'axios'

const DB_NOT_CONFIGURED_MSG = '数据库未配置'

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Response interceptor — unwrap { code, message, data }
http.interceptors.response.use(
  (response: AxiosResponse) => {
    const body = response.data
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return Promise.reject(new Error(body.message || 'API Error'))
    }
    return response
  },
  (error: AxiosError<{ detail?: string }>) => {
    // Detect "DB not configured" 400 response and attach a flag
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

/** Check if an error is the "DB not configured" case */
export function isDbError(err: unknown): boolean {
  return typeof err === 'object' && err !== null && 'isDbNotConfigured' in err && (err as any).isDbNotConfigured === true
}

export default http
