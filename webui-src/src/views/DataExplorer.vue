<template>
  <div>
    <n-card title="数据浏览" size="small">
      <template #header-extra>
        <n-space>
          <n-tag size="small" :type="isDbMode ? 'success' : 'default'">
            存储: {{ saveMode || '-' }}
          </n-tag>
          <!-- A-14: 搜索框 -->
          <n-input
            v-model:value="keyword"
            placeholder="搜索文件名/表名"
            clearable
            size="small"
            style="width: 180px"
          />
          <n-select
            v-model:value="platform"
            :options="platformOptions"
            placeholder="选择平台"
            style="width: 140px"
            @update:value="onPlatformChange"
          />
          <n-select
            v-if="!isDbMode"
            v-model:value="fileType"
            :options="typeOptions"
            placeholder="文件类型"
            style="width: 120px"
            @update:value="loadData"
          />
          <n-button @click="loadData" size="small">刷新</n-button>
        </n-space>
      </template>

      <n-spin :show="loading">
        <n-empty v-if="!loading && !filteredDataFiles.length" description="暂无数据，请先运行爬虫采集" />
        <n-data-table
          v-else
          :columns="currentColumns"
          :data="filteredDataFiles"
          size="small"
          :row-key="(r: any) => r.path || r.table"
        />
      </n-spin>

      <!-- DB 模式下同时展示文件数据 -->
      <template v-if="isDbMode">
        <n-divider />
        <n-space justify="space-between" align="center" style="margin-bottom: 8px">
          <span class="text-sm font-medium">文件数据 <n-tag size="small" type="info">file</n-tag></span>
          <n-select
            v-model:value="fileType"
            :options="typeOptions"
            placeholder="文件类型"
            style="width: 120px"
            @update:value="loadFileData"
          />
        </n-space>
        <n-spin :show="fileLoading">
          <n-empty v-if="!fileLoading && !filteredFileDataList.length" description="暂无文件数据" />
          <n-data-table
            v-else
            :columns="fileColumns"
            :data="filteredFileDataList"
            size="small"
            :row-key="(r: any) => r.path"
          />
        </n-spin>
      </template>
    </n-card>

    <!-- Preview Modal -->
    <n-modal v-model:show="showPreview" :title="'预览: ' + previewFile" preset="card" style="width: 80vw; max-width: 900px">
      <n-spin :show="previewing">
        <div v-if="previewType === 'json'" class="max-h-[60vh] overflow-auto">
          <n-data-table v-if="previewRows.length" :columns="previewColumns" :data="previewRows" size="small" :max-height="400" virtual-scroll />
          <pre v-else class="text-xs">{{ previewRaw }}</pre>
        </div>
        <div v-else class="max-h-[60vh] overflow-auto">
          <n-data-table v-if="previewRows.length" :columns="previewColumns" :data="previewRows" size="small" :max-height="400" virtual-scroll />
          <pre v-else class="text-xs">{{ previewRaw }}</pre>
        </div>
      </n-spin>
    </n-modal>

    <!-- Stats -->
    <n-card title="数据统计" size="small" class="mt-4">
      <n-spin :show="statsLoading">
        <n-descriptions bordered :column="3" size="small" v-if="!isDbMode">
          <n-descriptions-item label="文件总数">{{ stats.total_files }}</n-descriptions-item>
          <n-descriptions-item label="总大小">{{ formatSize(stats.total_size) }}</n-descriptions-item>
          <n-descriptions-item label="涉及平台">{{ stats.by_platform ? Object.keys(stats.by_platform).join(', ') : '-' }}</n-descriptions-item>
        </n-descriptions>
        <n-descriptions bordered :column="3" size="small" v-else>
          <n-descriptions-item label="总记录数">{{ stats.total_records ?? 0 }}</n-descriptions-item>
          <n-descriptions-item label="表数量">{{ (stats.by_table || []).length }}</n-descriptions-item>
          <n-descriptions-item label="主要表">{{ (stats.by_table || []).map((x: any) => x.table).join(', ') || '-' }}</n-descriptions-item>
        </n-descriptions>
      </n-spin>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted, computed } from 'vue'
import { NButton, NTag, NSpace, useMessage } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import http, { unwrapApiData } from '@/api'

const message = useMessage()
const loading = ref(false)
const statsLoading = ref(false)
const previewing = ref(false)
const showPreview = ref(false)

const platform = ref('')
const fileType = ref('')
const keyword = ref('')  // A-14: 搜索关键词
const dataFiles = ref<any[]>([])
const stats = ref<any>({})
const saveMode = ref('')

const isDbMode = computed(() => ['sqlite', 'db', 'postgres'].includes((saveMode.value || '').toLowerCase()))

// File data for mixed mode (DB mode also shows files)
const fileDataList = ref<any[]>([])
const fileLoading = ref(false)

// A-14: 过滤后的数据表
const filteredDataFiles = computed(() => {
  if (!keyword.value) return dataFiles.value
  const kw = keyword.value.toLowerCase()
  return dataFiles.value.filter(r =>
    (r.name || '').toLowerCase().includes(kw) ||
    (r.path || '').toLowerCase().includes(kw) ||
    (r.table || '').toLowerCase().includes(kw)
  )
})

const filteredFileDataList = computed(() => {
  if (!keyword.value) return fileDataList.value
  const kw = keyword.value.toLowerCase()
  return fileDataList.value.filter(r =>
    (r.name || '').toLowerCase().includes(kw) ||
    (r.path || '').toLowerCase().includes(kw)
  )
})

const previewFile = ref('')
const previewType = ref('json')
const previewRaw = ref('')
const previewRows = ref<any[]>([])
const previewColumns = ref<DataTableColumn[]>([])

const platformOptions = [
  { label: '全部', value: '' },
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: '快手', value: 'ks' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
  { label: '贴吧', value: 'tieba' },
  { label: '知乎', value: 'zhihu' },
  { label: '微信', value: 'wechat' },
]

const typeOptions = [
  { label: '全部', value: '' },
  { label: 'JSON', value: 'json' },
  { label: 'CSV', value: 'csv' },
  { label: 'Excel', value: 'xlsx' },
]

const fileColumns: DataTableColumn[] = [
  { title: '文件名', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '平台',
    key: 'path',
    width: 80,
    render: (row: any) => {
      const parts = (row.path || '').split(/[/\\]/)
      return h(NTag, { size: 'small', type: 'info' }, () => parts[0] || '-')
    },
  },
  {
    title: '类型',
    key: 'type',
    width: 70,
    render: (row: any) => h(NTag, { size: 'small' }, () => (row.type || '').toUpperCase()),
  },
  { title: '记录数', key: 'record_count', width: 80, render: (row: any) => row.record_count ?? '-' },
  { title: '大小', key: 'size', width: 90, render: (row: any) => formatSize(row.size) },
  {
    title: '修改时间',
    key: 'modified_at',
    width: 160,
    render: (row: any) => {
      if (!row.modified_at) return '-'
      return new Date(row.modified_at * 1000).toLocaleString()
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', onClick: () => previewData(row) }, () => '预览'),
        h(NButton, { size: 'tiny', type: 'primary', tag: 'a', href: `/api/data/download/${encodeURIComponent(row.path)}`, target: '_blank' } as any, () => '下载'),
      ]),
  },
]

const dbColumns: DataTableColumn[] = [
  { title: '表', key: 'table', ellipsis: { tooltip: true } },
  { title: '记录数', key: 'count', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row: any) => h(NSpace, { size: 'small' }, () => [
      h(NButton, { size: 'tiny', onClick: () => previewDb(row) }, () => '预览'),
    ]),
  },
]

const currentColumns = computed(() => isDbMode.value ? dbColumns : fileColumns)

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function onPlatformChange() {
  loadData()
  if (isDbMode.value) loadFileData()
}

async function loadFileData() {
  fileLoading.value = true
  try {
    const params: any = {}
    if (platform.value) params.platform = platform.value
    if (fileType.value) params.file_type = fileType.value
    const { data } = await http.get('/data/files', { params })
    const payload = unwrapApiData<any>(data) || {}
    fileDataList.value = payload.files || []
  } catch {
    fileDataList.value = []
  } finally {
    fileLoading.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    if (isDbMode.value) {
      const params: any = {}
      if (platform.value) params.platform = platform.value
      const { data } = await http.get('/data/db/tables', { params })
      const payload = unwrapApiData<any>(data) || {}
      dataFiles.value = payload.items || []
    } else {
      const params: any = {}
      if (platform.value) params.platform = platform.value
      if (fileType.value) params.file_type = fileType.value
      const { data } = await http.get('/data/files', { params })
      const payload = unwrapApiData<any>(data) || {}
      dataFiles.value = payload.files || []
    }
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    if (isDbMode.value) {
      const { data } = await http.get('/data/db/stats')
      stats.value = unwrapApiData<any>(data) || {}
    } else {
      const { data } = await http.get('/data/stats')
      stats.value = unwrapApiData<any>(data) || {}
    }
  } catch {
    // silent
  } finally {
    statsLoading.value = false
  }
}

async function loadSaveMode() {
  try {
    const { data } = await http.get('/config/validate')
    saveMode.value = (data.data?.save_data_option || '').toLowerCase()
  } catch {
    saveMode.value = ''
  }
}

async function previewData(row: any) {
  previewFile.value = row.name
  previewType.value = row.type || 'json'
  previewRaw.value = ''
  previewRows.value = []
  previewColumns.value = []
  showPreview.value = true
  previewing.value = true

  try {
    const { data } = await http.get(`/data/files/${encodeURIComponent(row.path)}`, { params: { preview: true } })
    const content = unwrapApiData<any>(data)

    if (Array.isArray(content)) {
      previewRows.value = content.slice(0, 100)
      if (content.length > 0) {
        previewColumns.value = Object.keys(content[0]).map(k => ({
          title: k,
          key: k,
          width: 150,
          ellipsis: { tooltip: true },
        }))
      }
    } else if (content.records && Array.isArray(content.records)) {
      previewRows.value = content.records.slice(0, 100)
      if (content.records.length > 0) {
        previewColumns.value = Object.keys(content.records[0]).map(k => ({
          title: k,
          key: k,
          width: 150,
          ellipsis: { tooltip: true },
        }))
      }
    } else {
      previewRaw.value = typeof content === 'string' ? content : JSON.stringify(content, null, 2)
    }
  } catch (e: any) {
    previewRaw.value = '预览失败: ' + (e.message || '未知错误')
  } finally {
    previewing.value = false
  }
}

async function previewDb(row: any) {
  previewFile.value = row.table
  previewType.value = 'db'
  previewRaw.value = ''
  previewRows.value = []
  previewColumns.value = []
  showPreview.value = true
  previewing.value = true

  try {
    const { data } = await http.get('/data/db/records', { params: { table: row.table, limit: 100 } })
    const payload = unwrapApiData<any>(data) || {}
    const records = payload.records || []
    previewRows.value = records
    if (records.length > 0) {
      previewColumns.value = Object.keys(records[0]).map(k => ({
        title: k,
        key: k,
        width: 150,
        ellipsis: { tooltip: true },
      }))
    }
  } catch (e: any) {
    previewRaw.value = '预览失败: ' + (e.message || '未知错误')
  } finally {
    previewing.value = false
  }
}

onMounted(() => {
  loadSaveMode().finally(() => {
    loadData()
    loadStats()
    // In DB mode, also load file data for mixed browsing
    if (isDbMode.value) {
      loadFileData()
    }
  })
})
</script>
