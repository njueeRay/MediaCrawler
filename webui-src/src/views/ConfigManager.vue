<template>
  <div>
    <n-spin :show="loading">
      <n-tabs type="line" animated v-model:value="activeTab">
        <n-tab-pane v-for="group in configGroups" :key="group.key" :name="group.key" :tab="group.label">
          <n-card>
            <n-form label-placement="left" label-width="180">
              <n-form-item v-for="field in group.fields" :key="field.key" :label="field.label">
                <template v-if="field.type === 'password'">
                  <n-input
                    v-model:value="formValues[field.key]"
                    type="password"
                    show-password-on="click"
                    :placeholder="field.help"
                    style="max-width: 400px"
                  />
                </template>
                <template v-else-if="field.type === 'number'">
                  <n-input-number v-model:value="formValues[field.key]" :placeholder="field.help" style="max-width: 200px" />
                </template>
                <template v-else-if="field.type === 'select'">
                  <n-select
                    v-model:value="formValues[field.key]"
                    :options="field.options"
                    :placeholder="field.help"
                    style="max-width: 300px"
                  />
                </template>
                <template v-else-if="field.type === 'switch'">
                  <n-switch v-model:value="formValues[field.key]" />
                </template>
                <template v-else>
                  <n-input v-model:value="formValues[field.key]" :placeholder="field.help" style="max-width: 400px" />
                </template>
                <span v-if="field.help" class="ml-2 text-xs text-gray-400">{{ field.help }}</span>
              </n-form-item>
            </n-form>
            <n-space class="mt-4">
              <n-button type="primary" :loading="saving" @click="saveConfig">保存配置</n-button>
              <n-button v-if="testableGroups.includes(group.key)" :loading="testing" @click="testConnection(group.key)">
                测试连接
              </n-button>
            </n-space>
          </n-card>
        </n-tab-pane>

        <!-- Config History Tab -->
        <n-tab-pane name="_history" tab="变更历史">
          <n-card>
            <n-spin :show="historyLoading">
              <n-data-table :columns="historyColumns" :data="historyItems" size="small" />
              <n-empty v-if="!historyLoading && !historyItems.length" description="暂无变更记录" />
            </n-spin>
            <n-space class="mt-3" justify="end">
              <n-pagination v-model:page="historyPage" :page-count="historyPageCount" @update:page="loadHistory" />
            </n-space>
          </n-card>
        </n-tab-pane>
      </n-tabs>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted, watch } from 'vue'
import { NTag, useMessage } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import http, { isDbError } from '@/api'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const historyLoading = ref(false)
const activeTab = ref('')
const configGroups = ref<any[]>([])
const formValues = ref<Record<string, any>>({})

const historyItems = ref<any[]>([])
const historyPage = ref(1)
const historyPageCount = ref(1)

// Groups that support "test connection"
const testableGroups = ['feishu', 'database', 'wechat']

/** 将后端字符串值转为前端组件需要的类型 */
function coerceValue(field: any, raw: string): any {
  if (field.type === 'switch') {
    if (raw === '' || raw === undefined || raw === null) return false
    return ['true', '1', 'yes', 'on'].includes(String(raw).toLowerCase())
  }
  if (field.type === 'number') {
    if (raw === '' || raw === undefined || raw === null) return null
    const n = Number(raw)
    return isNaN(n) ? null : n
  }
  return raw ?? ''
}

/** 将前端组件值转回字符串写入 .env */
function serializeValue(field: any, val: any): string | null {
  if (val === undefined || val === null) return null
  if (field.type === 'switch') return val ? 'true' : 'false'
  if (field.sensitive && val === '****') return null // 不覆盖敏感值
  return String(val)
}

const historyColumns: DataTableColumn[] = [
  { title: '配置项', key: 'config_key' },
  { title: '旧值', key: 'old_value', width: 180, ellipsis: { tooltip: true } },
  { title: '新值', key: 'new_value', width: 180, ellipsis: { tooltip: true } },
  {
    title: '分组', key: 'group', width: 80,
    render: (row: any) => h(NTag, { size: 'small' }, () => row.group || '-'),
  },
  { title: '时间', key: 'changed_at', width: 160 },
]

async function loadConfig() {
  loading.value = true
  try {
    const { data } = await http.get('/config/groups')
    configGroups.value = data.data?.groups || []
    for (const group of configGroups.value) {
      for (const field of group.fields) {
        formValues.value[field.key] = coerceValue(field, field.value)
      }
    }
    if (configGroups.value.length && !activeTab.value) {
      activeTab.value = configGroups.value[0].key
    }
  } catch (e: any) {
    message.error(e.message || '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const configs: Record<string, string> = {}
    // 构造 field lookup 以获取类型信息
    const fieldMap: Record<string, any> = {}
    for (const group of configGroups.value) {
      for (const field of group.fields) {
        fieldMap[field.key] = field
      }
    }
    for (const [key, value] of Object.entries(formValues.value)) {
      const field = fieldMap[key]
      if (!field) continue
      const serialized = serializeValue(field, value)
      if (serialized !== null) {
        configs[key] = serialized
      }
    }
    const { data } = await http.put('/config', { configs })
    message.success(data.message || '保存成功')
    loadConfig()
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnection(type: string) {
  testing.value = true
  try {
    const { data } = await http.post('/config/test', { type })
    if (data.data?.success) {
      message.success(`${type} 连接成功`)
    } else {
      message.warning(data.data?.error || `${type} 连接失败`)
    }
  } catch (e: any) {
    message.error(e.message || '测试失败')
  } finally {
    testing.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const { data } = await http.get('/config/history', { params: { page: historyPage.value, size: 20 } })
    historyItems.value = data.data?.items || []
    const total = data.data?.total || 0
    historyPageCount.value = Math.max(1, Math.ceil(total / 20))
  } catch (e: any) {
    if (isDbError(e)) historyItems.value = [{ config_key: '提示', old_value: '-', new_value: '需要数据库支持', group: '-', changed_at: '-' }]
  } finally {
    historyLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === '_history') loadHistory()
})

onMounted(loadConfig)
</script>
