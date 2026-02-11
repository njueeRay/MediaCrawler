<template>
  <div>
    <!-- Connection Status -->
    <n-card size="small" class="mb-4">
      <n-space align="center">
        <n-badge :type="feishuConnected ? 'success' : 'error'" dot />
        <span>飞书连接: {{ feishuConnected ? '已连接' : '未连接' }}</span>
        <n-button size="small" @click="checkConnection" :loading="checking">检测</n-button>
        <n-button size="small" type="primary" @click="$router.push({ name: 'ConfigManager' })">前往配置</n-button>
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
          <n-button type="primary" :loading="syncing" :disabled="!feishuConnected || !syncForm.mapping_scheme_id" @click="startSync">
            开始同步
          </n-button>
        </n-form-item>
      </n-form>
    </n-card>

    <!-- Sync History -->
    <n-card title="同步历史" size="small">
      <template #header-extra>
        <n-button size="small" @click="loadHistory">刷新</n-button>
      </template>

      <n-spin :show="loading">
        <n-data-table :columns="columns" :data="histories" size="small" />
        <n-empty v-if="!loading && !histories.length" description="暂无同步记录" />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted, watch } from 'vue'
import { NTag, useMessage } from 'naive-ui'
import http from '@/api'

const message = useMessage()
const loading = ref(false)
const checking = ref(false)
const syncing = ref(false)
const feishuConnected = ref(false)
const histories = ref<any[]>([])
const schemeOptions = ref<any[]>([])

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
    feishuConnected.value = data.data?.connected || false
    if (!feishuConnected.value) {
      message.warning(data.data?.error || '飞书未连接，请先配置 App ID 和 Secret')
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
    const items = data.data?.items || []
    schemeOptions.value = items.map((s: any) => ({ label: s.name, value: s.id }))
    // auto-select default
    const dft = items.find((s: any) => s.is_default)
    if (dft) syncForm.value.mapping_scheme_id = dft.id
    else if (items.length) syncForm.value.mapping_scheme_id = items[0].id
    else syncForm.value.mapping_scheme_id = null
  } catch {
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

async function loadHistory() {
  loading.value = true
  try {
    const { data } = await http.get('/feishu/history')
    histories.value = data.data?.items || []
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  checkConnection()
  loadSchemes()
  loadHistory()
})
</script>
