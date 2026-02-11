<template>
  <div>
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

    <!-- Subscription List -->
    <n-card title="我的订阅" size="small">
      <template #header-extra>
        <n-space>
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
          :pagination="pagination"
          :remote="true"
          @update:page="handlePageChange"
        />
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
import { ref, h, onMounted } from 'vue'
import { NButton, NTag, NSpace, useMessage } from 'naive-ui'
import http from '@/api'

const message = useMessage()
const loading = ref(false)
const searching = ref(false)
const adding = ref(false)
const showAdd = ref(false)

const searchPlatform = ref('xhs')
const searchKeyword = ref('')
const filterPlatform = ref('')

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
    title: '平台',
    key: 'platform',
    width: 80,
    render: (row: any) => h(NTag, { type: 'info', size: 'small' }, () => platformLabels[row.platform] || row.platform),
  },
  { title: '创作者', key: 'creator_name', ellipsis: { tooltip: true } },
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
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const { data } = await http.get('/subscribe/stats')
    subStats.value = data.data || {}
  } catch {
    // silent
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page
  loadSubscriptions()
}

async function searchCreators() {
  if (!searchKeyword.value) return
  searching.value = true
  try {
    const { data } = await http.post('/subscribe/search', {
      platform: searchPlatform.value,
      keyword: searchKeyword.value,
    })
    const items = data.data?.items || []
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
})
</script>
