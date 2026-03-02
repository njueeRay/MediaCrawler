/**
 * Auth Store — JWT access/refresh token 管理（S-01/W-01）
 *
 * - accessToken  存储于 localStorage['mc_access_token']
 * - refreshToken 存储于 localStorage['mc_refresh_token']
 * - AUTH_ENABLED=false 时后端返回 dummy token，登录流程照常走，无需前端特判
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/api'

export interface UserInfo {
  id: number
  username: string
  is_admin: boolean
  email: string | null
}

const TOKEN_KEY = 'mc_access_token'
const REFRESH_KEY = 'mc_refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const refreshToken = ref<string | null>(localStorage.getItem(REFRESH_KEY))
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)

  // ── 内部工具 ──────────────────────────────────────────────────────────────

  function _setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  }

  function _clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }

  // ── 公开 API ──────────────────────────────────────────────────────────────

  async function login(username: string, password: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const resp = await http.post('/auth/login', { username, password })
      const { access_token, refresh_token } = resp.data
      _setTokens(access_token, refresh_token)
      await fetchUser()
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ||
        e?.message ||
        '登录失败，请检查用户名和密码'
      error.value = msg
      throw new Error(msg)
    } finally {
      loading.value = false
    }
  }

  async function fetchUser(): Promise<void> {
    try {
      const resp = await http.get('/auth/me')
      user.value = resp.data
    } catch {
      // 获取用户信息失败不影响已存 token
      user.value = null
    }
  }

  /**
   * 使用 refresh_token 换取新 access_token。
   * 成功返回 true，失败（token 过期/无效）清空登录态并返回 false。
   */
  async function refreshAccessToken(): Promise<boolean> {
    const rt = refreshToken.value
    if (!rt) return false
    try {
      const resp = await http.post('/auth/refresh', { refresh_token: rt })
      const { access_token, refresh_token: newRt } = resp.data
      _setTokens(access_token, newRt ?? rt)
      return true
    } catch {
      _clearTokens()
      return false
    }
  }

  function logout() {
    _clearTokens()
  }

  return {
    accessToken,
    refreshToken,
    user,
    loading,
    error,
    isAuthenticated,
    login,
    logout,
    fetchUser,
    refreshAccessToken,
    clearTokens: _clearTokens,
  }
})
