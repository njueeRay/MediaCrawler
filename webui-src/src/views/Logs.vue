<template>
  <div>
    <n-card title="实时日志" size="small">
      <template #header-extra>
        <n-space>
          <n-select
            v-model:value="logLevel"
            :options="levelOptions"
            placeholder="日志级别"
            style="width: 120px"
          />
          <n-badge :type="wsConnected ? 'success' : 'error'" dot>
            <span class="text-sm">{{ wsConnected ? 'WS 已连接' : 'WS 断开' }}</span>
          </n-badge>
          <n-button size="small" :loading="loadingHistory" @click="loadHistoryLogs">加载历史</n-button>
          <n-button size="small" @click="connectWs">重连</n-button>
          <n-button size="small" @click="logs = []">清空</n-button>
        </n-space>
      </template>

      <div
        ref="logContainer"
        class="h-[500px] overflow-y-auto bg-gray-900 text-gray-100 p-4 rounded font-mono text-sm leading-6"
      >
        <div v-for="log in filteredLogs" :key="log.id" :class="logClass(log.level)">
          <span class="text-gray-500 mr-2">{{ log.timestamp }}</span>
          <span class="mr-2">[{{ log.level.toUpperCase() }}]</span>
          <span>{{ log.message }}</span>
        </div>
        <div v-if="!filteredLogs.length" class="text-gray-500">等待日志...</div>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import http from '@/api'

interface LogItem {
  id: number
  timestamp: string
  level: string
  message: string
}

const logContainer = ref<HTMLElement | null>(null)
const logs = ref<LogItem[]>([])
const logLevel = ref('all')
const wsConnected = ref(false)
const loadingHistory = ref(false)
let ws: WebSocket | null = null
let logId = 0

const levelOptions = [
  { label: '全部', value: 'all' },
  { label: 'Info', value: 'info' },
  { label: 'Warning', value: 'warning' },
  { label: 'Error', value: 'error' },
]

const filteredLogs = computed(() => {
  if (logLevel.value === 'all') return logs.value
  return logs.value.filter(l => l.level === logLevel.value)
})

function logClass(level: string) {
  switch (level) {
    case 'error': return 'text-red-400'
    case 'warning': return 'text-yellow-400'
    case 'success': return 'text-green-400'
    case 'debug': return 'text-gray-400'
    default: return ''
  }
}

function connectWs() {
  if (ws) {
    ws.close()
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  ws = new WebSocket(`${protocol}//${host}/api/ws/logs`)

  ws.onopen = () => {
    wsConnected.value = true
    addLog('info', 'WebSocket 已连接')
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      addLog(data.level || 'info', data.message || event.data)
    } catch {
      addLog('info', event.data)
    }
  }

  ws.onclose = () => {
    wsConnected.value = false
    addLog('warning', 'WebSocket 断开连接')
  }

  ws.onerror = () => {
    wsConnected.value = false
    addLog('error', 'WebSocket 连接错误')
  }
}

function addLog(level: string, message: string) {
  logs.value.push({
    id: ++logId,
    timestamp: new Date().toLocaleTimeString(),
    level,
    message,
  })
  // Keep max 1000 entries
  if (logs.value.length > 1000) {
    logs.value = logs.value.slice(-500)
  }
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

onMounted(connectWs)

onUnmounted(() => {
  if (ws) ws.close()
})

async function loadHistoryLogs() {
  loadingHistory.value = true
  try {
    const res = await http.get('/crawler/logs', { params: { limit: 200 } })
    const entries: Array<{ level: string; message: string; timestamp?: string }> = res.data?.data ?? res.data ?? []
    const historyItems: LogItem[] = entries.map((e) => ({
      id: ++logId,
      timestamp: e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '--',
      level: e.level || 'info',
      message: e.message || '',
    }))
    logs.value = [...historyItems, ...logs.value]
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    })
  } catch (err: any) {
    addLog('error', '加载历史日志失败: ' + (err.message || err))
  } finally {
    loadingHistory.value = false
  }
}
</script>
