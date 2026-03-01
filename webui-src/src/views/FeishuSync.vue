<template>
  <div>
    <DbRequiredAlert v-if="dbNotReady" />
    <!-- Connection Status -->
    <n-card size="small" class="mb-4">
      <n-space align="center">
        <n-badge :type="feishuConnected ? 'success' : 'error'" dot />
        <span>飞书连接: {{ feishuConnected ? '已连接' : '未连接' }}</span>
        <n-button size="small" @click="checkConnection" :loading="checking">检测</n-button>
        <n-button size="small" type="primary" @click="$router.push({ name: 'ConfigManager' })">前往配置</n-button>
      </n-space>
    </n-card>

    <!-- Live Sync Progress -->
    <n-card v-if="syncProgress.active" title="同步进行中" size="small" class="mb-4">
      <n-space vertical>
        <n-progress type="line" :percentage="syncProgress.percentage" :status="syncProgressStatus" indicator-placement="inside" :processing="syncProgress.status === 'running'" />
        <n-space :size="24">
          <n-statistic label="已处理行" :value="syncProgress.lineCount" />
          <n-statistic label="成功" :value="syncProgress.successCount">
            <template #suffix><span class="text-green-500 text-xs"> 条</span></template>
          </n-statistic>
          <n-statistic label="失败" :value="syncProgress.failedCount">
            <template #suffix><span class="text-red-500 text-xs"> 条</span></template>
          </n-statistic>
          <n-statistic v-if="syncProgress.totalRecords" label="总记录" :value="syncProgress.totalRecords" />
        </n-space>
        <n-log :rows="6" :log="syncProgress.logText" class="mt-2" />
      </n-space>
    </n-card>

    <!-- Sync Form -->
    <n-card title="新建同步" size="small" class="mb-4">
      <n-form inline label-placement="left" label-width="80">
        <n-form-item label="平台">
          <n-select v-model:value="syncForm.platform" :options="platformOptions" style="width: 120px" />
        </n-form-item>
        <n-form-item label="数据类型">
          <n-select v-model:value="syncForm.data_type" :options="dataTypeOptions" style="width: 120px" />
        </n-form-item>
        <n-form-item label="映射方案">
          <n-select
            v-model:value="syncForm.mapping_scheme_id"
            :options="schemeOptions"
            style="width: 200px"
            placeholder="选择映射方案"
          />
        </n-form-item>
        <n-form-item label="时间范围">
          <n-select v-model:value="syncForm.date_range_type" :options="dateRangeOptions" style="width: 140px" />
        </n-form-item>
        <n-form-item>
          <n-button type="primary" :loading="syncing" :disabled="!feishuConnected || !syncForm.mapping_scheme_id || syncProgress.active" @click="startSync">
            开始同步
          </n-button>
        </n-form-item>
      </n-form>
    </n-card>

    <!-- Sync History -->
    <n-card title="同步历史" size="small">
      <template #header-extra>
        <n-space size="small">
          <n-popconfirm
            @positive-click="cleanupHistory('failed')"
            positive-text="确认清理"
            negative-text="取消"
          >
            <template #trigger>
              <n-button size="small" type="warning">清理失败记录</n-button>
            </template>
            将删除 7 天内所有 failed 状态的历史记录，确认？
          </n-popconfirm>
          <n-button size="small" @click="loadHistory">刷新</n-button>
        </n-space>
      </template>

      <n-spin :show="loading">
        <n-data-table :columns="columns" :data="histories" size="small" />
        <n-empty v-if="!loading && !histories.length" description="暂无同步记录" />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, h, computed, onMounted, onUnmounted, watch } from 'vue'
import { NTag, NPopconfirm, NSpace, useMessage } from 'naive-ui'
import http, { isDbError, unwrapApiData } from '@/api'
import DbRequiredAlert from '@/components/common/DbRequiredAlert.vue'

const message = useMessage()
const loading = ref(false)
const checking = ref(false)
const syncing = ref(false)
const feishuConnected = ref(false)
const histories = ref<any[]>([])
const schemeOptions = ref<any[]>([])
const dbNotReady = ref(false)

// WebSocket sync progress
const syncProgress = ref({
  active: false,
  status: 'running' as 'running' | 'success' | 'failed',
  historyId: 0,
  lineCount: 0,
  successCount: 0,
  failedCount: 0,
  totalRecords: 0,
  logText: '',
  percentage: 0,
})

const syncProgressStatus = computed(() => {
  if (syncProgress.value.status === 'success') return 'success'
  if (syncProgress.value.status === 'failed') return 'error'
  return undefined
})

let ws: WebSocket | null = null
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null
let wsReconnectDelay = 3000
const WS_MAX_RECONNECT_DELAY = 60000
const WS_MAX_RECONNECT_ATTEMPTS = 20
let wsReconnectAttempts = 0

function connectSyncWS() {
  if (ws && ws.readyState <= 1) return // already connecting or open
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/api/ws/sync`
  ws = new WebSocket(url)

  ws.onopen = () => {
    wsReconnectDelay = 3000
    wsReconnectAttempts = 0
  }

  ws.onmessage = (event) => {
    if (event.data === 'ping') {
      ws?.send('pong')
      return
    }
    try {
      const data = JSON.parse(event.data)
      handleSyncEvent(data)
    } catch { /* ignore non-JSON */ }
  }

  ws.onclose = () => {
    // Exponential backoff reconnect while component is mounted
    wsReconnectAttempts++
    if (wsReconnectAttempts <= WS_MAX_RECONNECT_ATTEMPTS) {
      wsReconnectTimer = setTimeout(connectSyncWS, wsReconnectDelay)
      wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_MAX_RECONNECT_DELAY)
    }
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function handleSyncEvent(data: any) {
  if (data.type === 'sync_start') {
    syncProgress.value = {
      active: true,
      status: 'running',
      historyId: data.history_id,
      lineCount: 0,
      successCount: 0,
      failedCount: 0,
      totalRecords: 0,
      logText: '',
      percentage: 0,
    }
    message.info(data.message || '同步已开始')
  } else if (data.type === 'sync_progress') {
    syncProgress.value.lineCount = data.line_count || 0
    syncProgress.value.successCount = data.success_count || 0
    syncProgress.value.failedCount = data.failed_count || 0
    syncProgress.value.totalRecords = data.total_records || 0
    if (data.line) {
      syncProgress.value.logText += data.line + '\n'
    }
    // Estimate percentage from total_records
    const total = data.total_records || 0
    const done = (data.success_count || 0) + (data.failed_count || 0)
    syncProgress.value.percentage = total > 0 ? Math.min(99, Math.round((done / total) * 100)) : 0
  } else if (data.type === 'sync_complete') {
    syncProgress.value.status = data.status === 'success' ? 'success' : 'failed'
    syncProgress.value.successCount = data.success_count || 0
    syncProgress.value.failedCount = data.failed_count || 0
    syncProgress.value.totalRecords = data.total_records || 0
    syncProgress.value.percentage = 100
    if (data.status === 'success') {
      message.success(`同步完成: ${data.success_count} 条成功, 耗时 ${data.duration}s`)
    } else {
      message.error(`同步失败: ${data.error || '未知错误'}`)
    }
    // Auto-hide progress after a delay, reload history
    setTimeout(() => { syncProgress.value.active = false }, 5000)
    loadHistory()
  }
}

function disconnectSyncWS() {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
  wsReconnectTimer = null
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
}

const syncForm = ref({
  platform: 'xhs',
  data_type: 'note',
  mapping_scheme_id: null as number | null,
  date_range_type: 'all',
  batch_size: 500,
})

const platformOptions = [
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
  { label: '微信', value: 'wechat' },
]

const dataTypeOptions = [
  { label: '笔记/视频', value: 'note' },
  { label: '文章', value: 'article' },
  { label: '评论', value: 'comment' },
]

const dateRangeOptions = [
  { label: '全部', value: 'all' },
  { label: '上次同步后', value: 'since_last' },
]

const columns = [
  { title: '平台', key: 'platform', width: 80 },
  { title: '数据类型', key: 'data_type', width: 100 },
  { title: '映射方案', key: 'mapping_scheme_name' },
  { title: '总数', key: 'total_records', width: 60 },
  { title: '成功', key: 'success_count', width: 60 },
  { title: '失败', key: 'failed_count', width: 60 },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render: (row: any) => {
      const typeMap: Record<string, string> = {
        running: 'info', success: 'success', partial: 'warning', failed: 'error',
      }
      return h(NTag, { size: 'small', type: (typeMap[row.status] || 'default') as any }, () => row.status)
    },
  },
  { title: '开始时间', key: 'started_at', width: 160 },
  { title: '耗时(秒)', key: 'duration_seconds', width: 80 },
]

async function checkConnection() {
  checking.value = true
  try {
    const { data } = await http.get('/feishu/status')
    const payload = unwrapApiData<any>(data) || {}
    feishuConnected.value = payload.connected || false
    if (!feishuConnected.value) {
      message.warning(payload.error || '飞书未连接，请先配置 App ID 和 Secret')
    } else {
      message.success('飞书连接正常')
    }
  } catch (e: any) {
    message.error(e.message || '检测失败')
  } finally {
    checking.value = false
  }
}

async function loadSchemes() {
  try {
    const params: any = {}
    if (syncForm.value.platform) params.platform = syncForm.value.platform
    if (syncForm.value.data_type) params.data_type = syncForm.value.data_type
    const { data } = await http.get('/mapping/schemes', { params })
    const payload = unwrapApiData<any>(data) || {}
    const items = payload.items || []
    schemeOptions.value = items.map((s: any) => ({ label: s.name, value: s.id }))
    const dft = items.find((s: any) => s.is_default)
    if (dft) syncForm.value.mapping_scheme_id = dft.id
    else if (items.length) syncForm.value.mapping_scheme_id = items[0].id
    else syncForm.value.mapping_scheme_id = null
  } catch (e: any) {
    if (isDbError(e)) dbNotReady.value = true
    schemeOptions.value = []
  }
}

watch(() => [syncForm.value.platform, syncForm.value.data_type], loadSchemes)

async function startSync() {
  syncing.value = true
  try {
    const { data } = await http.post('/feishu/sync', {
      platform: syncForm.value.platform,
      data_type: syncForm.value.data_type,
      mapping_scheme_id: syncForm.value.mapping_scheme_id,
      date_range_type: syncForm.value.date_range_type,
      batch_size: syncForm.value.batch_size,
    })
    message.success(data.message || '同步任务已创建')
    loadHistory()
  } catch (e: any) {
    message.error(e.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function cleanupHistory(status?: string) {
  try {
    const params: any = { keep_days: 7 }
    if (status) params.status = status
    const { data } = await http.delete('/feishu/history', { params })
    const payload = unwrapApiData<any>(data) || {}
    message.success(`已删除 ${payload.deleted ?? 0} 条记录`)
    loadHistory()
  } catch (e: any) {
    message.error(e.message || '清理失败')
  }
}

async function loadHistory() {
  loading.value = true
  try {
    const { data } = await http.get('/feishu/history')
    const payload = unwrapApiData<any>(data) || {}
    histories.value = payload.items || []
  } catch (e: any) {
    if (isDbError(e)) dbNotReady.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  checkConnection()
  loadSchemes()
  loadHistory()
  connectSyncWS()
})

onUnmounted(() => {
  disconnectSyncWS()
})
</script>
