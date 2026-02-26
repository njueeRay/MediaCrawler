<template>
  <div>
    <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen" :item-responsive="true">
      <!-- Crawler Status -->
      <n-gi span="4 m:1">
        <n-card size="small">
          <n-statistic label="爬虫状态">
            <template #prefix>
              <n-badge :type="crawlerBadgeType" dot style="margin-right: 6px" />
            </template>
            {{ crawlerLabel }}
          </n-statistic>
          <template #action>
            <n-space size="small">
              <n-button size="tiny" type="primary" :disabled="crawlerRunning" @click="$router.push({ name: 'Logs' })">查看日志</n-button>
              <n-button size="tiny" type="error" :disabled="!crawlerRunning" @click="stopCrawler">停止</n-button>
            </n-space>
          </template>
        </n-card>
      </n-gi>
      <!-- Subscriptions -->
      <n-gi span="4 m:1">
        <n-card size="small" hoverable @click="$router.push({ name: 'Subscription' })">
          <n-statistic label="订阅创作者" :value="dashboard.subscriptions.total">
            <template #suffix>
              <span class="text-xs text-gray-400"> / {{ dashboard.subscriptions.active }} 活跃</span>
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <!-- Data Files -->
      <n-gi span="4 m:1">
        <n-card size="small" hoverable @click="$router.push({ name: 'DataExplorer' })">
          <n-statistic label="数据文件" :value="dashboard.data.total_files">
            <template #suffix>
              <span class="text-xs text-gray-400"> ({{ formatSize(dashboard.data.total_size) }})</span>
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <!-- Scheduler -->
      <n-gi span="4 m:1">
        <n-card size="small" hoverable @click="$router.push({ name: 'TaskScheduler' })">
          <n-statistic label="定时任务" :value="dashboard.scheduler.active_tasks">
            <template #suffix>
              <span class="text-xs text-gray-400"> / {{ dashboard.scheduler.total_executions }} 次执行</span>
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Crawler Detail + Quick Actions -->
    <n-grid :x-gap="16" :y-gap="16" :cols="2" class="mt-4" responsive="screen" :item-responsive="true">
      <n-gi span="2 m:1">
        <n-card title="爬虫信息" size="small">
          <n-descriptions bordered :column="1" size="small">
            <n-descriptions-item label="状态">
              <n-tag :type="crawlerBadgeType" size="small">{{ crawlerLabel }}</n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="平台">{{ dashboard.crawler.platform || '-' }}</n-descriptions-item>
            <n-descriptions-item label="模式">{{ dashboard.crawler.crawler_type || '-' }}</n-descriptions-item>
            <n-descriptions-item label="启动时间">{{ dashboard.crawler.started_at || '-' }}</n-descriptions-item>
          </n-descriptions>
        </n-card>
      </n-gi>
      <n-gi span="2 m:1">
        <n-card title="快捷操作" size="small">
          <n-space vertical>
            <n-button block type="primary" @click="$router.push({ name: 'ConfigManager' })">系统配置</n-button>
            <n-button block @click="$router.push({ name: 'Subscription' })">管理订阅</n-button>
            <n-button block @click="$router.push({ name: 'DataExplorer' })">浏览数据</n-button>
            <n-button block @click="$router.push({ name: 'FeishuSync' })">同步飞书</n-button>
          </n-space>
        </n-card>
      </n-gi>
      <n-gi span="2 m:1">
        <n-card title="订阅采集队列" size="small">
          <n-descriptions bordered :column="1" size="small">
            <n-descriptions-item label="运行中">{{ queueStats.running }}</n-descriptions-item>
            <n-descriptions-item label="排队中">{{ queueStats.queued }}</n-descriptions-item>
            <n-descriptions-item label="成功">{{ queueStats.success }}</n-descriptions-item>
            <n-descriptions-item label="失败">{{ queueStats.failed }}</n-descriptions-item>
            <n-descriptions-item label="队列长度">{{ queueStats.queue_size }}</n-descriptions-item>
          </n-descriptions>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Recent Logs -->
    <n-card title="最近日志" size="small" class="mt-4">
      <template #header-extra>
        <n-space size="small">
          <span class="text-xs text-gray-400">{{ lastRefreshText }}</span>
          <n-button size="small" text @click="$router.push({ name: 'Logs' })">查看全部</n-button>
        </n-space>
      </template>
      <div class="bg-gray-900 text-gray-100 p-3 rounded font-mono text-xs leading-5 max-h-48 overflow-y-auto">
        <div v-for="log in recentLogs" :key="log.timestamp + log.message">
          <span class="text-gray-500">{{ log.timestamp }} </span>
          <span :class="logLevelClass(log.level)">{{ log.message }}</span>
        </div>
        <div v-if="!recentLogs.length" class="text-gray-500">暂无日志</div>
      </div>
    </n-card>

    <!-- Platform Data Distribution -->
    <n-card title="平台数据分布" size="small" class="mt-4" v-if="platformList.length">
      <div v-for="p in platformList" :key="p.name" class="flex items-center gap-3 mb-2">
        <span class="w-16 text-sm font-medium truncate">{{ platformLabels[p.name] || p.name }}</span>
        <n-progress
          type="line"
          :percentage="dashboard.data.total_files ? Math.round(p.files / dashboard.data.total_files * 100) : 0"
          :height="16"
          :show-indicator="false"
          :color="platformColors[p.name] || '#63e2b7'"
          class="flex-1"
        />
        <span class="text-xs text-gray-400 w-24 text-right">{{ p.files }} 文件 / {{ formatSize(p.size) }}</span>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import http, { unwrapApiData } from '@/api'

const message = useMessage()

const dashboard = ref({
  crawler: { status: 'idle', platform: '', crawler_type: '', started_at: '' },
  data: { total_files: 0, total_size: 0, platforms: [] as string[], by_platform: {} as Record<string, { files: number; size: number }> },
  subscriptions: { total: 0, active: 0 },
  scheduler: { active_tasks: 0, total_executions: 0 },
})

const recentLogs = ref<Array<{ timestamp: string; level: string; message: string }>>([])
const queueStats = ref({ queue_size: 0, running: 0, queued: 0, success: 0, failed: 0 })
const lastRefreshAt = ref('')

const platformLabels: Record<string, string> = {
  xhs: '小红书', dy: '抖音', ks: '快手', bili: 'B站', wb: '微博', wechat: '微信', tieba: '贴吧', zhihu: '知乎',
}
const platformColors: Record<string, string> = {
  xhs: '#ff2442', dy: '#000000', ks: '#ff4500', bili: '#00a1d6', wb: '#ff8200', wechat: '#07c160', tieba: '#4e6ef2', zhihu: '#0066ff',
}
const platformList = computed(() => {
  const bp = dashboard.value.data.by_platform || {}
  return Object.entries(bp)
    .map(([name, stat]) => ({ name, files: stat.files, size: stat.size }))
    .sort((a, b) => b.files - a.files)
})

const statusLabelMap: Record<string, string> = {
  idle: '空闲', running: '运行中', stopping: '停止中', error: '异常',
}
const crawlerLabel = computed(() => statusLabelMap[dashboard.value.crawler.status] || dashboard.value.crawler.status)
const crawlerRunning = computed(() => dashboard.value.crawler.status === 'running')
const crawlerBadgeType = computed(() => {
  const m: Record<string, string> = { idle: 'default', running: 'success', stopping: 'warning', error: 'error' }
  return (m[dashboard.value.crawler.status] || 'default') as any
})
const lastRefreshText = computed(() => lastRefreshAt.value ? `刷新于 ${lastRefreshAt.value}` : '未刷新')

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB'
  return (bytes / 1073741824).toFixed(1) + ' GB'
}

function logLevelClass(level: string) {
  switch (level) {
    case 'error': return 'text-red-400'
    case 'warning': return 'text-yellow-400'
    default: return ''
  }
}

async function stopCrawler() {
  try {
    await http.post('/crawler/stop')
    message.success('已发送停止指令')
    loadDashboard()
  } catch (e: any) {
    message.error(e.message || '停止失败')
  }
}

async function loadDashboard() {
  try {
    const { data } = await http.get('/dashboard')
    const d = unwrapApiData<any>(data) || {}
    dashboard.value.crawler = d.crawler || dashboard.value.crawler
    dashboard.value.data = d.data || dashboard.value.data
    dashboard.value.subscriptions = d.subscriptions || dashboard.value.subscriptions
    dashboard.value.scheduler = d.scheduler || dashboard.value.scheduler
  } catch {
    // 降级：至少获取 health
    try {
      await http.get('/health')
    } catch {
      // offline
    }
  }
}

async function loadLogs() {
  try {
    const { data } = await http.get('/crawler/logs', { params: { limit: 20 } })
    const payload = unwrapApiData<any>(data)
    const logs = Array.isArray(payload) ? payload : (payload?.logs || [])
    recentLogs.value = logs.slice(-20)
  } catch {
    // silent
  }
}

async function loadQueueStats() {
  try {
    const { data } = await http.get('/subscribe/crawl/status')
    const payload = unwrapApiData<any>(data) || {}
    const items = payload.items || []
    const next = { queue_size: payload.queue_size || 0, running: 0, queued: 0, success: 0, failed: 0 }
    for (const item of items) {
      if (item.status === 'running') next.running += 1
      else if (item.status === 'queued') next.queued += 1
      else if (item.status === 'success') next.success += 1
      else if (item.status === 'failed') next.failed += 1
    }
    queueStats.value = next
  } catch {
    // silent
  }
}

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadDashboard()
  loadLogs()
  loadQueueStats()
  lastRefreshAt.value = new Date().toLocaleTimeString()
  // Auto-refresh every 30s
  refreshTimer = setInterval(() => {
    loadDashboard()
    loadLogs()
    loadQueueStats()
    lastRefreshAt.value = new Date().toLocaleTimeString()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>
