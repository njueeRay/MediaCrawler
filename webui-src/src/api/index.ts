import axios from 'axios'
import type { AxiosInstance, AxiosResponse } from 'axios'

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
  (error) => {
    return Promise.reject(error)
  },
)

export default http
