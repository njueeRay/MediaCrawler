<template>
  <div>
    <DbRequiredAlert v-if="dbNotReady" />
    <!-- Stats -->
    <n-grid :x-gap="12" :y-gap="12" :cols="3" class="mb-4">
      <n-gi>
        <n-card size="small"><n-statistic label="总订阅" :value="subStats.total" /></n-card>
      </n-gi>
      <n-gi>
        <n-card size="small"><n-statistic label="活跃" :value="subStats.active" /></n-card>
      </n-gi>
      <n-gi>
        <n-card size="small">
          <n-statistic label="平台分布">
            <span class="text-sm">{{ Object.keys(subStats.by_platform || {}).length }} 个平台</span>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Search -->
    <n-card size="small" class="mb-4">
      <n-space>
        <n-select
          v-model:value="searchPlatform"
          :options="platformOptions"
          placeholder="选择平台"
          style="width: 160px"
        />
        <n-input v-model:value="searchKeyword" placeholder="搜索创作者..." clearable style="width: 240px" />
        <n-button type="primary" @click="searchCreators" :loading="searching">搜索</n-button>
        <n-button @click="showAdd = true">手动添加</n-button>
      </n-space>
    </n-card>

    <!-- Search Results -->
    <n-card v-if="searchResults.length" title="搜索结果" size="small" class="mb-4">
      <template #header-extra>
        <n-button size="small" quaternary @click="searchResults = []">清除</n-button>
      </template>
      <n-list hoverable clickable>
        <n-list-item v-for="item in searchResults" :key="item.creator_id">
          <template #prefix>
            <n-avatar v-if="item.creator_avatar" :src="item.creator_avatar" :size="36" round />
            <n-avatar v-else :size="36" round>{{ (item.creator_name || '?')[0] }}</n-avatar>
          </template>
          <n-thing>
            <template #header>
              <n-space align="center" :size="8">
                <span>{{ item.creator_name }}</span>
                <n-tag size="small" :bordered="false">{{ platformLabels[searchPlatform] }}</n-tag>
              </n-space>
            </template>
            <template #description>
              <span class="text-xs text-gray-400">ID: {{ item.creator_id }}</span>
              <template v-if="item.meta">
                <span v-if="item.meta.fans" class="ml-3 text-xs">粉丝: {{ item.meta.fans }}</span>
                <span v-if="item.meta.followers_count" class="ml-3 text-xs">粉丝: {{ item.meta.followers_count }}</span>
                <span v-if="item.meta.videos" class="ml-3 text-xs">视频: {{ item.meta.videos }}</span>
              </template>
            </template>
          </n-thing>
          <template #suffix>
            <n-button
              size="small"
              :type="item._subscribed ? 'default' : 'primary'"
              :disabled="item._subscribed"
              :loading="item._subscribing"
              @click="quickSubscribe(item)"
            >
              {{ item._subscribed ? '已订阅' : '订阅' }}
            </n-button>
          </template>
        </n-list-item>
      </n-list>
    </n-card>

    <!-- Subscription List -->
    <n-card title="我的订阅" size="small">
      <template #header-extra>
        <n-space>
          <n-button
            size="small"
            type="primary"
            :disabled="!checkedRowKeys.length"
            :loading="batchCrawling"
            @click="batchTriggerCrawl"
          >
            批量采集({{ checkedRowKeys.length }})
          </n-button>
          <n-select
            v-model:value="filterPlatform"
            :options="[{ label: '全部平台', value: '' }, ...platformOptions]"
            style="width: 140px"
            @update:value="loadSubscriptions"
          />
          <n-button @click="loadSubscriptions" size="small">刷新</n-button>
        </n-space>
      </template>

      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="subscriptions"
          :row-key="(row: any) => row.id"
          v-model:checked-row-keys="checkedRowKeys"
          :pagination="pagination"
          :remote="true"
          @update:page="handlePageChange"
        />
        <n-empty v-if="!loading && !subscriptions.length && !dbNotReady" description="暂无订阅，请通过搜索或手动添加创建" class="py-8" />
      </n-spin>
    </n-card>

    <!-- Add Subscription Modal -->
    <n-modal v-model:show="showAdd" title="手动添加订阅" preset="dialog" style="width: 480px">
      <n-form label-placement="left" label-width="90">
        <n-form-item label="平台" required>
          <n-select v-model:value="addForm.platform" :options="platformOptions" />
        </n-form-item>
        <n-form-item label="创作者ID" required>
          <n-input v-model:value="addForm.creator_id" placeholder="平台上的唯一 ID" />
        </n-form-item>
        <n-form-item label="创作者名称" required>
          <n-input v-model:value="addForm.creator_name" placeholder="显示名称" />
        </n-form-item>
        <n-form-item label="主页URL">
          <n-input v-model:value="addForm.creator_url" placeholder="可选" />
        </n-form-item>
        <n-form-item label="自动采集">
          <n-switch v-model:value="addForm.auto_crawl" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="addForm.notes" type="textarea" :rows="2" placeholder="可选" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showAdd = false">取消</n-button>
        <n-button type="primary" :loading="adding" @click="createSubscription">确认添加</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted, onBeforeUnmount } from 'vue'
import { NButton, NTag, NSpace, useMessage } from 'naive-ui'
import http, { isDbError } from '@/api'
import DbRequiredAlert from '@/components/common/DbRequiredAlert.vue'

const message = useMessage()
const loading = ref(false)
const searching = ref(false)
const adding = ref(false)
const showAdd = ref(false)
const dbNotReady = ref(false)
const batchCrawling = ref(false)

const checkedRowKeys = ref<number[]>([])
const crawlStatusMap = ref<Record<number, { status: string; message: string; updated_at: string }>>({})
let crawlStatusTimer: any = null

const searchPlatform = ref('bili')
const searchKeyword = ref('')
const filterPlatform = ref('')
const searchResults = ref<any[]>([])

const subscriptions = ref<any[]>([])
const subStats = ref<any>({ total: 0, active: 0, by_platform: {} })
const pagination = ref({ page: 1, pageSize: 20, itemCount: 0 })

const addForm = ref({
  platform: 'xhs',
  creator_id: '',
  creator_name: '',
  creator_url: '',
  auto_crawl: true,
  notes: '',
})

const platformOptions = [
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: '快手', value: 'ks' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
  { label: '微信', value: 'wechat' },
  { label: '贴吧', value: 'tieba' },
  { label: '知乎', value: 'zhihu' },
]

const platformLabels: Record<string, string> = Object.fromEntries(
  platformOptions.map(p => [p.value, p.label])
)

const columns = [
  {
    type: 'selection',
    key: 'selection',
    width: 50,
  },
  {
    title: '平台',
    key: 'platform',
    width: 80,
    render: (row: any) => h(NTag, { type: 'info', size: 'small' }, () => platformLabels[row.platform] || row.platform),
  },
  { title: '创作者', key: 'creator_name', ellipsis: { tooltip: true } },
  {
    title: '采集状态',
    key: 'crawl_status',
    width: 120,
    render: (row: any) => {
      const st = crawlStatusMap.value[row.id]
      if (!st) return h('span', { class: 'text-xs text-gray-400' }, '—')
      const typeMap: Record<string, any> = {
        queued: 'warning',
        running: 'info',
        success: 'success',
        failed: 'error',
      }
      return h(NTag, { size: 'small', type: typeMap[st.status] || 'default' }, () => st.status)
    },
  },
  { title: '内容数', key: 'content_count', width: 80 },
  {
    title: '状态',
    key: 'is_active',
    width: 80,
    render: (row: any) => h(NTag, { type: row.is_active ? 'success' : 'default', size: 'small' }, () => row.is_active ? '活跃' : '暂停'),
  },
  {
    title: '自动采集',
    key: 'auto_crawl',
    width: 80,
    render: (row: any) => row.auto_crawl ? '是' : '否',
  },
  { title: '最后采集', key: 'last_crawled_at', width: 160 },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => triggerCrawl(row.id) }, () => '采集'),
        h(NButton, { size: 'tiny', onClick: () => toggleActive(row) }, () => row.is_active ? '暂停' : '恢复'),
        h(NButton, { size: 'tiny', type: 'error', onClick: () => deleteSub(row.id) }, () => '删除'),
      ]),
  },
]

async function loadSubscriptions() {
  loading.value = true
  try {
    const params: any = { page: pagination.value.page, size: pagination.value.pageSize }
    if (filterPlatform.value) params.platform = filterPlatform.value
    const { data } = await http.get('/subscribe', { params })
    subscriptions.value = data.data?.items || []
    pagination.value.itemCount = data.data?.total || 0
    // 每次加载列表后刷新一次状态
    await loadCrawlStatuses()
  } catch (e: any) {
    if (isDbError(e)) { dbNotReady.value = true; return }
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadCrawlStatuses() {
  const ids = subscriptions.value.map((s: any) => s.id).filter((x: any) => typeof x === 'number')
  if (!ids.length) return
  try {
    const { data } = await http.get('/subscribe/crawl/status', { params: { ids: ids.join(',') } })
    const items = data.data?.items || []
    const next: any = { ...crawlStatusMap.value }
    for (const it of items) {
      next[it.sub_id] = { status: it.status, message: it.message, updated_at: it.updated_at }
    }
    crawlStatusMap.value = next
  } catch {
    // ignore
  }
}

async function batchTriggerCrawl() {
  if (!checkedRowKeys.value.length) return
  batchCrawling.value = true
  try {
    const { data } = await http.post('/subscribe/crawl/batch', { ids: checkedRowKeys.value })
    message.success(data.message || '已入队')
    await loadCrawlStatuses()
  } catch (e: any) {
    message.error(e.message || '批量采集失败')
  } finally {
    batchCrawling.value = false
  }
}

async function loadStats() {
  try {
    const { data } = await http.get('/subscribe/stats')
    subStats.value = data.data || {}
  } catch (e: any) {
    if (isDbError(e)) dbNotReady.value = true
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page
  loadSubscriptions()
}

async function searchCreators() {
  if (!searchKeyword.value) return
  searching.value = true
  searchResults.value = []
  try {
    const { data } = await http.post('/subscribe/search', {
      platform: searchPlatform.value,
      keyword: searchKeyword.value,
    })
    const items = (data.data?.items || []).map((it: any) => ({
      ...it,
      _subscribed: false,
      _subscribing: false,
    }))
    searchResults.value = items
    if (items.length) {
      message.info(`搜索到 ${items.length} 个创作者`)
    } else {
      message.warning('未找到创作者，您可以手动添加订阅')
    }
  } catch (e: any) {
    message.error(e.message || '搜索失败')
  } finally {
    searching.value = false
  }
}

async function quickSubscribe(item: any) {
  item._subscribing = true
  try {
    await http.post('/subscribe', {
      platform: searchPlatform.value,
      creator_id: item.creator_id,
      creator_name: item.creator_name,
      creator_url: item.creator_url || '',
      auto_crawl: true,
    })
    item._subscribed = true
    message.success(`已订阅 ${item.creator_name}`)
    loadSubscriptions()
    loadStats()
  } catch (e: any) {
    message.error(e.message || '订阅失败')
  } finally {
    item._subscribing = false
  }
}

async function createSubscription() {
  if (!addForm.value.creator_id || !addForm.value.creator_name) {
    message.warning('请填写创作者 ID 和名称')
    return
  }
  adding.value = true
  try {
    const { data } = await http.post('/subscribe', addForm.value)
    message.success(data.message || '订阅成功')
    showAdd.value = false
    addForm.value = { platform: 'xhs', creator_id: '', creator_name: '', creator_url: '', auto_crawl: true, notes: '' }
    loadSubscriptions()
    loadStats()
  } catch (e: any) {
    message.error(e.message || '添加失败')
  } finally {
    adding.value = false
  }
}

async function triggerCrawl(id: number) {
  try {
    const { data } = await http.post(`/subscribe/${id}/crawl`)
    message.success(data.message || '已触发采集')
  } catch (e: any) {
    message.error(e.message || '操作失败')
  }
}

async function toggleActive(row: any) {
  try {
    await http.put(`/subscribe/${row.id}`, { is_active: !row.is_active })
    message.success(row.is_active ? '已暂停' : '已恢复')
    loadSubscriptions()
  } catch (e: any) {
    message.error(e.message || '操作失败')
  }
}

async function deleteSub(id: number) {
  try {
    await http.delete(`/subscribe/${id}`)
    message.success('已取消订阅')
    loadSubscriptions()
    loadStats()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

onMounted(() => {
  loadSubscriptions()
  loadStats()

  // 轮询采集队列状态（轻量）
  crawlStatusTimer = setInterval(() => {
    loadCrawlStatuses()
  }, 2000)
})

onBeforeUnmount(() => {
  if (crawlStatusTimer) {
    clearInterval(crawlStatusTimer)
    crawlStatusTimer = null
  }
})
</script>
