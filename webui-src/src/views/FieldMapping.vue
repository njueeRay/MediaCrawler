<template>
  <div>
    <!-- Filters + Create -->
    <n-card size="small" class="mb-4">
      <n-space>
        <n-select v-model:value="platform" :options="platformOptions" placeholder="平台" style="width: 140px" @update:value="loadSchemes" />
        <n-select v-model:value="dataType" :options="dataTypeOptions" placeholder="数据类型" style="width: 140px" @update:value="loadSchemes" />
        <n-button type="primary" @click="showCreate = true">新建方案</n-button>
      </n-space>
    </n-card>

    <!-- Scheme List (when no detail open) -->
    <template v-if="!activeScheme">
      <n-spin :show="loading">
        <n-data-table :columns="columns" :data="schemes" size="small" />
      </n-spin>
    </template>

    <!-- Scheme Detail Editor -->
    <template v-else>
      <n-card size="small" class="mb-4">
        <template #header>
          <n-space align="center">
            <n-button text @click="activeScheme = null">← 返回列表</n-button>
            <n-divider vertical />
            <span>{{ activeScheme.name }}</span>
            <n-tag size="small" :type="activeScheme.is_system ? 'warning' : 'default'">{{ activeScheme.is_system ? '系统' : '自定义' }}</n-tag>
          </n-space>
        </template>
        <template #header-extra>
          <n-space>
            <n-button size="small" @click="showPreview = true" :disabled="!activeScheme.items?.length">预览效果</n-button>
            <n-button size="small" type="primary" @click="saveSchemeItems" :loading="saving">保存</n-button>
          </n-space>
        </template>

        <n-data-table :columns="itemColumns" :data="editItems" size="small" :max-height="500" />

        <n-space class="mt-3">
          <n-button size="small" dashed @click="addItem">+ 添加字段</n-button>
        </n-space>
      </n-card>
    </template>

    <!-- Create Modal -->
    <n-modal v-model:show="showCreate" title="新建映射方案" preset="dialog" style="width: 500px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="方案名称"><n-input v-model:value="newScheme.name" placeholder="例: 自定义导出" /></n-form-item>
        <n-form-item label="平台"><n-select v-model:value="newScheme.platform" :options="platformOptions.filter(o => o.value)" /></n-form-item>
        <n-form-item label="数据类型"><n-select v-model:value="newScheme.data_type" :options="dataTypeOptions.filter(o => o.value)" /></n-form-item>
        <n-form-item label="描述"><n-input v-model:value="newScheme.description" type="textarea" /></n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showCreate = false">取消</n-button>
        <n-button type="primary" @click="createScheme">创建</n-button>
      </template>
    </n-modal>

    <!-- Preview Modal -->
    <n-modal v-model:show="showPreview" title="映射预览" preset="card" style="width: 80vw; max-width: 900px">
      <n-spin :show="previewing">
        <n-data-table v-if="previewData.length" :columns="previewColumns" :data="previewData" size="small" :max-height="400" />
        <n-empty v-else description="暂无预览数据（需要先有采集数据）" />
      </n-spin>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { NTag, NButton, NInput, NSelect, NSwitch, NSpace, useMessage } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import http from '@/api'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const showCreate = ref(false)
const showPreview = ref(false)

const platform = ref('')
const dataType = ref('')
const schemes = ref<any[]>([])
const activeScheme = ref<any>(null)
const editItems = ref<any[]>([])
const previewData = ref<any[]>([])
const previewColumns = ref<DataTableColumn[]>([])

const platformOptions = [
  { label: '全部', value: '' },
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
  { label: '微信', value: 'wechat' },
]

const dataTypeOptions = [
  { label: '全部', value: '' },
  { label: '笔记/视频', value: 'note' },
  { label: '评论', value: 'comment' },
  { label: '文章', value: 'article' },
  { label: '视频', value: 'video' },
]

const transformOptions = [
  { label: '原样', value: 'none' },
  { label: '时间戳→日期', value: 'timestamp_to_date' },
  { label: '截断', value: 'truncate' },
  { label: '数字格式化', value: 'number_format' },
  { label: 'URL前缀', value: 'url_prefix' },
  { label: '值映射', value: 'map_value' },
  { label: 'JSON解析', value: 'json_parse' },
  { label: 'JSON转列表', value: 'json_to_list' },
]

const newScheme = ref({ name: '', platform: 'xhs', data_type: 'note', description: '' })

const columns: DataTableColumn[] = [
  { title: '方案名称', key: 'name' },
  {
    title: '平台', key: 'platform', width: 80,
    render: (row: any) => h(NTag, { size: 'small', type: 'info' }, () => row.platform),
  },
  { title: '数据类型', key: 'data_type', width: 100 },
  { title: '字段数', key: 'item_count', width: 80 },
  { title: '默认', key: 'is_default', width: 60, render: (row: any) => row.is_default ? '✓' : '' },
  {
    title: '类型', key: 'is_system', width: 80,
    render: (row: any) => h(NTag, { size: 'small', type: row.is_system ? 'warning' : 'default' }, () => row.is_system ? '系统' : '自定义'),
  },
  {
    title: '操作', key: 'actions', width: 160,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => openSchemeDetail(row.id) }, () => '编辑'),
        h(NButton, { size: 'tiny', type: 'error', disabled: row.is_system, onClick: () => deleteScheme(row.id) }, () => '删除'),
      ]),
  },
]

const itemColumns: DataTableColumn[] = [
  {
    title: '启用', key: 'enabled', width: 60,
    render: (row: any, idx: number) => h(NSwitch, { value: row.enabled, 'onUpdate:value': (v: boolean) => { editItems.value[idx].enabled = v } }),
  },
  {
    title: '源字段', key: 'source_field', width: 160,
    render: (row: any, idx: number) => h(NInput, { value: row.source_field, size: 'small', onUpdateValue: (v: string) => { editItems.value[idx].source_field = v } }),
  },
  {
    title: '显示名', key: 'display_name', width: 140,
    render: (row: any, idx: number) => h(NInput, { value: row.display_name, size: 'small', onUpdateValue: (v: string) => { editItems.value[idx].display_name = v } }),
  },
  {
    title: '转换', key: 'transform', width: 150,
    render: (row: any, idx: number) => h(NSelect, { value: row.transform, size: 'small', options: transformOptions, onUpdateValue: (v: string) => { editItems.value[idx].transform = v } }),
  },
  {
    title: '飞书类型', key: 'feishu_type', width: 100,
    render: (row: any, idx: number) => h(NInput, { value: row.feishu_type, size: 'small', onUpdateValue: (v: string) => { editItems.value[idx].feishu_type = v } }),
  },
  { title: '排序', key: 'sort_order', width: 60, render: (row: any) => row.sort_order },
  {
    title: '', key: 'del', width: 40,
    render: (_: any, idx: number) => h(NButton, { size: 'tiny', text: true, type: 'error', onClick: () => editItems.value.splice(idx, 1) }, () => '×'),
  },
]

async function loadSchemes() {
  loading.value = true
  try {
    const params: any = {}
    if (platform.value) params.platform = platform.value
    if (dataType.value) params.data_type = dataType.value
    const { data } = await http.get('/mapping/schemes', { params })
    schemes.value = data.data?.items || []
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function openSchemeDetail(id: number) {
  try {
    const { data } = await http.get(`/mapping/schemes/${id}`)
    activeScheme.value = data.data || {}
    editItems.value = (activeScheme.value.items || []).map((item: any, idx: number) => ({
      source_field: item.source_field,
      display_name: item.display_name,
      transform: item.transform || 'none',
      transform_config: item.transform_config || {},
      feishu_type: item.feishu_type || '1',
      enabled: item.enabled !== false,
      sort_order: item.sort_order ?? idx,
    }))
  } catch (e: any) {
    message.error(e.message || '加载方案详情失败')
  }
}

function addItem() {
  editItems.value.push({
    source_field: '',
    display_name: '',
    transform: 'none',
    transform_config: {},
    feishu_type: '1',
    enabled: true,
    sort_order: editItems.value.length,
  })
}

async function saveSchemeItems() {
  if (!activeScheme.value) return
  saving.value = true
  try {
    await http.put(`/mapping/schemes/${activeScheme.value.id}`, {
      name: activeScheme.value.name,
      description: activeScheme.value.description,
      items: editItems.value.map((item, idx) => ({ ...item, sort_order: idx })),
    })
    message.success('保存成功')
    loadSchemes()
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function createScheme() {
  try {
    await http.post('/mapping/schemes', newScheme.value)
    message.success('方案创建成功')
    showCreate.value = false
    loadSchemes()
  } catch (e: any) {
    message.error(e.message || '创建失败')
  }
}

async function deleteScheme(id: number) {
  try {
    await http.delete(`/mapping/schemes/${id}`)
    message.success('方案已删除')
    loadSchemes()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

onMounted(loadSchemes)
</script>
