<template>
  <div>
    <DbRequiredAlert v-if="dbNotReady" />
    <!-- Scheduler Status -->
    <n-card size="small" class="mb-4">
      <n-space align="center">
        <n-badge :type="schedulerStatus.running ? 'success' : 'default'" dot />
        <span>调度器: {{ schedulerStatus.running ? '运行中' : '未启动' }}</span>
        <span class="ml-4">活跃任务: {{ schedulerStatus.active_tasks }}</span>
        <span class="ml-4">总执行: {{ schedulerStatus.total_executions }} 次</span>
        <span v-if="schedulerStatus.next_run" class="ml-4 text-xs text-gray-400">下次执行: {{ schedulerStatus.next_run }}</span>
      </n-space>
    </n-card>

    <n-tabs type="line" animated>
      <!-- Task List -->
      <n-tab-pane name="tasks" tab="定时任务">
        <n-card size="small">
          <template #header-extra>
            <n-space>
              <n-button type="primary" size="small" @click="showCreate = true">新建任务</n-button>
              <n-button size="small" @click="loadTasks">刷新</n-button>
            </n-space>
          </template>
          <n-spin :show="loading">
            <n-data-table :columns="columns" :data="tasks" size="small" />
          </n-spin>
        </n-card>
      </n-tab-pane>

      <!-- Execution History -->
      <n-tab-pane name="history" tab="执行历史">
        <n-card size="small">
          <template #header-extra>
            <n-space>
              <n-select v-model:value="execFilter.status" :options="execStatusOptions" placeholder="状态" style="width: 120px" clearable @update:value="loadExecutions" />
              <n-button size="small" @click="loadExecutions">刷新</n-button>
            </n-space>
          </template>
          <n-spin :show="execLoading">
            <n-data-table :columns="execColumns" :data="executions" size="small" />
            <n-empty v-if="!execLoading && !executions.length" description="暂无执行记录" />
          </n-spin>
        </n-card>
      </n-tab-pane>
    </n-tabs>

    <!-- Execution Log Modal -->
    <n-modal v-model:show="showExecLog" title="执行日志" preset="dialog" style="width: 860px">
      <n-space vertical :size="10">
        <div class="text-xs text-gray-500">
          <span v-if="execLogMeta.execution_id">执行ID: {{ execLogMeta.execution_id }}</span>
          <span v-if="execLogMeta.status" class="ml-3">状态: {{ execLogMeta.status }}</span>
          <span v-if="execLogMeta.started_at" class="ml-3">开始: {{ execLogMeta.started_at }}</span>
          <span v-if="execLogMeta.finished_at" class="ml-3">结束: {{ execLogMeta.finished_at }}</span>
        </div>
        <n-log :log="execLogText" language="text" :rows="20" />
      </n-space>
      <template #action>
        <n-button @click="showExecLog = false">关闭</n-button>
      </template>
    </n-modal>

    <!-- Create / Edit Modal -->
    <n-modal v-model:show="showCreate" :title="editingTaskId ? '编辑定时任务' : '新建定时任务'" preset="dialog" style="width: 600px; max-height: 90vh; overflow-y: auto">
      <n-form label-placement="left" label-width="110">
        <n-form-item label="任务名称">
          <n-input v-model:value="newTask.name" placeholder="例: 每日微信采集&同步" />
        </n-form-item>
        <n-form-item label="任务类型">
          <n-select v-model:value="newTask.task_type" :options="taskTypeOptions" @update:value="onTaskTypeChange" />
        </n-form-item>
        <n-form-item label="平台">
          <n-select v-model:value="newTask.platform" :options="platformOptions" clearable />
        </n-form-item>
        <n-form-item label="调度类型">
          <n-select v-model:value="newTask.schedule_type" :options="scheduleTypeOptions" />
        </n-form-item>
        <n-form-item label="间隔(小时)" v-if="newTask.schedule_type === 'interval'">
          <n-input-number v-model:value="intervalHours" :min="1" />
        </n-form-item>
        <n-form-item label="Cron表达式" v-if="newTask.schedule_type === 'cron'">
          <n-input v-model:value="cronExpr" placeholder="例: 0 8 * * *" />
        </n-form-item>
      </n-form>

      <!-- Pipeline 配置：仅在 subscription_combo 类型下展示 -->
      <n-collapse v-if="newTask.task_type === 'subscription_combo'" class="mt-3">
        <n-collapse-item title="🔧 Pipeline 配置（采集 → 表1 → 过滤拉取 → JSON展开表2）" name="pipeline" :default-expanded="true">
          <n-form label-placement="left" label-width="110" size="small">
            <!-- Step 1: subscription_crawl -->
            <n-divider title-placement="left" class="text-xs">① 订阅采集</n-divider>
            <n-form-item label="采集数量上限">
              <n-input-number v-model:value="pipelineCfg.crawl_limit" :min="0" placeholder="0 = 不限" style="width:140px" />
              <span class="ml-2 text-xs text-gray-400">0 = 不限制</span>
            </n-form-item>
            <n-form-item label="超时(秒)">
              <n-input-number v-model:value="pipelineCfg.crawl_timeout" :min="60" style="width:140px" />
            </n-form-item>

            <!-- Step 2: feishu_push -->
            <n-divider title-placement="left" class="text-xs">② 同步到飞书表 1</n-divider>
            <n-form-item label="数据类型">
              <n-select v-model:value="pipelineCfg.data_type" :options="dataTypeOptions" style="width:140px" />
            </n-form-item>
            <n-form-item label="表1 ID" required>
              <n-input v-model:value="pipelineCfg.table1_id" placeholder="tblXXXXXXX" />
            </n-form-item>

            <!-- Step 3: feishu_pull -->
            <n-divider title-placement="left" class="text-xs">③ 过滤拉取（表1 → CSV）</n-divider>
            <n-form-item label="过滤字段">
              <n-input v-model:value="pipelineCfg.filter_field" placeholder="例: 信息质量评䉴" />
            </n-form-item>
            <n-form-item label="过滤运算">
              <n-select v-model:value="pipelineCfg.filter_operator" :options="filterOps" style="width:140px" />
            </n-form-item>
            <n-form-item label="过滤值">
              <n-dynamic-tags v-model:value="pipelineCfg.filter_values" />
            </n-form-item>
            <n-form-item label="视图 ID">
              <n-input v-model:value="pipelineCfg.view_id" placeholder="可空，空则使用默认视图" />
            </n-form-item>

            <!-- Step 4: feishu_push_json -->
            <n-divider title-placement="left" class="text-xs">④ JSON 展开推送表 2</n-divider>
            <n-form-item label="表2 ID" required>
              <n-input v-model:value="pipelineCfg.table2_id" placeholder="tblYYYYYYY" />
            </n-form-item>
            <n-form-item label="JSON 列名" required>
              <n-input v-model:value="pipelineCfg.json_columns" placeholder="例: AI文本分析" />
            </n-form-item>
            <n-form-item label="主键列">
              <n-input v-model:value="pipelineCfg.json_primary" placeholder="默认: 记录ID" />
            </n-form-item>
            <n-form-item label="范围起始">
              <n-input-number v-model:value="pipelineCfg.range_start" :min="1" placeholder="可空=全量" style="width:120px" />
              <span class="mx-2 text-xs">~</span>
              <n-input-number v-model:value="pipelineCfg.range_end" :min="1" placeholder="可空=全量" style="width:120px" />
            </n-form-item>
          </n-form>
        </n-collapse-item>
      </n-collapse>

      <template #action>
        <n-button @click="showCreate = false">取消</n-button>
        <n-button type="primary" @click="editingTaskId ? updateTask() : createTask()">{{ editingTaskId ? '保存' : '创建' }}</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { NTag, NButton, NSpace, useMessage, NLog } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import http, { isDbError, unwrapApiData } from '@/api'
import DbRequiredAlert from '@/components/common/DbRequiredAlert.vue'

const message = useMessage()
const loading = ref(false)
const execLoading = ref(false)
const showCreate = ref(false)
const editingTaskId = ref<number | null>(null)
const dbNotReady = ref(false)
const showExecLog = ref(false)
const execLogText = ref('')
const execLogMeta = ref<{ execution_id?: number; status?: string; started_at?: string; finished_at?: string }>({})

const schedulerStatus = ref({ running: false, active_tasks: 0, total_executions: 0, next_run: '' })
const tasks = ref<any[]>([])
const executions = ref<any[]>([])
const intervalHours = ref(6)
const cronExpr = ref('')
const execFilter = ref({ status: '' })

const newTask = ref({
  name: '',
  task_type: 'crawl',
  platform: 'xhs',
  schedule_type: 'interval',
})

const taskTypeOptions = [
  { label: '采集', value: 'crawl' },
  { label: '同步', value: 'sync' },
  { label: '采集+同步', value: 'combo' },
  { label: '订阅采集+全流程', value: 'subscription_combo' },
  { label: '清理', value: 'cleanup' },
]

const dataTypeOptions = [
  { label: '文章 (article)', value: 'article' },
  { label: '创作者 (creator)', value: 'creator' },
  { label: '笔记 (note)', value: 'note' },
]

const filterOps = [
  { label: 'contains', value: 'contains' },
  { label: 'is', value: 'is' },
  { label: 'isNot', value: 'isNot' },
  { label: 'isEmpty', value: 'isEmpty' },
  { label: 'isNotEmpty', value: 'isNotEmpty' },
]

// Pipeline 配置表单（subscription_combo 模式下需要）
const pipelineCfg = ref({
  // Step 1: subscription_crawl
  crawl_limit: 0,
  crawl_timeout: 3600,
  // Step 2: feishu_push
  data_type: 'creator',
  table1_id: '',
  // Step 3: feishu_pull
  filter_field: '',
  filter_operator: 'contains',
  filter_values: [] as string[],
  view_id: '',
  // Step 4: feishu_push_json
  table2_id: '',
  json_columns: '',
  json_primary: '记录ID',
  range_start: null as number | null,
  range_end: null as number | null,
})

function onTaskTypeChange(val: string) {
  // subscription_combo 默认选微信平台
  if (val === 'subscription_combo' && !newTask.value.platform) {
    newTask.value.platform = 'wechat'
  }
}

const platformOptions = [
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
  { label: '微信', value: 'wechat' },
  { label: '快手', value: 'ks' },
  { label: '贴吧', value: 'tieba' },
  { label: '知乎', value: 'zhihu' },
]

const scheduleTypeOptions = [
  { label: '固定间隔', value: 'interval' },
  { label: 'Cron 表达式', value: 'cron' },
  { label: '执行一次', value: 'once' },
]

const execStatusOptions = [
  { label: '运行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
]

const columns: DataTableColumn[] = [
  { title: '名称', key: 'name' },
  {
    title: '类型', key: 'task_type', width: 80,
    render: (row: any) => h(NTag, { size: 'small' }, () => row.task_type),
  },
  { title: '平台', key: 'platform', width: 80 },
  {
    title: '状态', key: 'is_active', width: 80,
    render: (row: any) => h(NTag, { size: 'small', type: row.is_active ? 'success' : 'default' }, () => row.is_active ? '启用' : '禁用'),
  },
  { title: '执行次数', key: 'run_count', width: 80 },
  { title: '失败次数', key: 'fail_count', width: 80 },
  { title: '上次执行', key: 'last_run_at', width: 160 },
  { title: '下次执行', key: 'next_run_at', width: 160 },
  {
    title: '调度',
    key: 'schedule',
    width: 160,
    ellipsis: { tooltip: true },
    render: (row: any) => {
      if (!row.schedule_type) return '-'
      if (row.schedule_type === 'interval') {
        const h = row.schedule_config?.hours
        return `每 ${h || '-'} 小时`
      }
      if (row.schedule_type === 'cron') {
        return row.schedule_config?.cron || 'cron'
      }
      return row.schedule_type
    },
  },
  {
    title: '操作', key: 'actions', width: 260,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => triggerTask(row.id) }, () => '执行'),
        h(NButton, { size: 'tiny', type: 'info', onClick: () => openEdit(row) }, () => '编辑'),
        h(NButton, { size: 'tiny', onClick: () => toggleTask(row) }, () => row.is_active ? '禁用' : '启用'),
        h(NButton, { size: 'tiny', type: 'error', onClick: () => deleteTask(row.id) }, () => '删除'),
      ]),
  },
]

const execColumns: DataTableColumn[] = [
  { title: '任务', key: 'task_name', width: 160 },
  {
    title: '触发方式', key: 'trigger_type', width: 80,
    render: (row: any) => h(NTag, { size: 'small' }, () => row.trigger_type === 'manual' ? '手动' : '定时'),
  },
  {
    title: '状态', key: 'status', width: 80,
    render: (row: any) => {
      const m: Record<string, string> = { running: 'info', success: 'success', failed: 'error', cancelled: 'default' }
      return h(NTag, { size: 'small', type: (m[row.status] || 'default') as any }, () => row.status)
    },
  },
  { title: '开始', key: 'started_at', width: 160 },
  { title: '结束', key: 'finished_at', width: 160 },
  { title: '耗时(秒)', key: 'duration_seconds', width: 80 },
  { title: '错误', key: 'error_message', ellipsis: { tooltip: true } },
  {
    title: '日志',
    key: 'log',
    width: 80,
    render: (row: any) => h(NButton, { size: 'tiny', onClick: () => openExecutionLog(row.id) }, () => '查看'),
  },
]

async function openExecutionLog(executionId: number) {
  execLogText.value = ''
  execLogMeta.value = { execution_id: executionId }
  showExecLog.value = true
  try {
    const { data } = await http.get(`/scheduler/executions/${executionId}/logs`)
    const payload = unwrapApiData<any>(data) || {}
    execLogText.value = payload.log || ''
    execLogMeta.value = {
      execution_id: payload.execution_id,
      status: payload.status,
      started_at: payload.started_at,
      finished_at: payload.finished_at,
    }
  } catch (e: any) {
    execLogText.value = `加载失败: ${e.message || e}`
  }
}

async function loadStatus() {
  try {
    const { data } = await http.get('/scheduler/status')
    schedulerStatus.value = unwrapApiData<any>(data) || {}
  } catch (e: any) {
    if (isDbError(e)) dbNotReady.value = true
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const { data } = await http.get('/scheduler/tasks')
    const payload = unwrapApiData<any>(data) || {}
    tasks.value = payload.items || []
  } catch (e: any) {
    if (isDbError(e)) { dbNotReady.value = true; return }
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadExecutions() {
  execLoading.value = true
  try {
    const params: any = { size: 50 }
    if (execFilter.value.status) params.status = execFilter.value.status
    const { data } = await http.get('/scheduler/executions', { params })
    const payload = unwrapApiData<any>(data) || {}
    executions.value = payload.items || []
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    execLoading.value = false
  }
}

async function createTask() {
  if (!newTask.value.name.trim()) { message.warning('请填写任务名称'); return }
  if (newTask.value.schedule_type === 'cron' && !cronExpr.value.trim()) { message.warning('请填写 Cron 表达式'); return }
  try {
    const scheduleConfig: any = {}
    if (newTask.value.schedule_type === 'interval') scheduleConfig.hours = intervalHours.value
    if (newTask.value.schedule_type === 'cron') scheduleConfig.cron = cronExpr.value

    // 构建 task_config
    let taskConfig: any = {}
    if (newTask.value.task_type === 'subscription_combo') {
      // Pipeline 模式：将表单字段序列化为 pipeline 步骤数组
      const cfg = pipelineCfg.value
      const pipeline: any[] = []

      // Step 1
      const step1: any = { step: 'subscription_crawl', platform: newTask.value.platform }
      if (cfg.crawl_limit > 0) step1.limit = cfg.crawl_limit
      if (cfg.crawl_timeout !== 3600) step1.timeout_seconds = cfg.crawl_timeout
      pipeline.push(step1)

      // Step 2
      const step2: any = { step: 'feishu_push', platform: newTask.value.platform, data_type: cfg.data_type }
      if (cfg.table1_id) step2.table_id = cfg.table1_id
      pipeline.push(step2)

      // Step 3 (可选）
      if (cfg.table1_id) {
        const step3: any = {
          step: 'feishu_pull',
          table_id: cfg.table1_id,
          platform: newTask.value.platform,
          output: 'step3_csv',
        }
        if (cfg.filter_field && cfg.filter_values.length) {
          step3.filter_field = cfg.filter_field
          step3.filter_operator = cfg.filter_operator
          step3.filter_values = cfg.filter_values
        }
        if (cfg.view_id) step3.view_id = cfg.view_id
        pipeline.push(step3)
      }

      // Step 4 (可选）
      if (cfg.table2_id && cfg.json_columns) {
        const step4: any = {
          step: 'feishu_push_json',
          input: 'step3_csv',
          table_id: cfg.table2_id,
          json_columns: cfg.json_columns,
          json_primary: cfg.json_primary || '记录ID',
        }
        if (cfg.range_start) step4.range_start = cfg.range_start
        if (cfg.range_end) step4.range_end = cfg.range_end
        pipeline.push(step4)
      }

      taskConfig = { pipeline }
    }

    await http.post('/scheduler/tasks', {
      ...newTask.value,
      schedule_config: scheduleConfig,
      task_config: taskConfig,
    })
    message.success('任务创建成功')
    showCreate.value = false
    editingTaskId.value = null
    loadTasks()
    loadStatus()
  } catch (e: any) {
    message.error(e.message || '创建失败')
  }
}

function openEdit(row: any) {
  editingTaskId.value = row.id
  newTask.value = {
    name: row.name || '',
    task_type: row.task_type || 'crawl',
    platform: row.platform || 'xhs',
    schedule_type: row.schedule_type || 'interval',
  }
  if (row.schedule_type === 'interval') {
    intervalHours.value = row.schedule_config?.hours || 6
  } else if (row.schedule_type === 'cron') {
    cronExpr.value = row.schedule_config?.cron || ''
  }
  // 恢复 pipeline 配置（如果有）
  if (row.task_config?.pipeline) {
    const steps = row.task_config.pipeline
    for (const s of steps) {
      if (s.step === 'subscription_crawl') {
        pipelineCfg.value.crawl_limit = s.limit || 0
        pipelineCfg.value.crawl_timeout = s.timeout_seconds || 3600
      }
      if (s.step === 'feishu_push') {
        pipelineCfg.value.data_type = s.data_type || 'creator'
        pipelineCfg.value.table1_id = s.table_id || ''
      }
      if (s.step === 'feishu_pull') {
        pipelineCfg.value.filter_field = s.filter_field || ''
        pipelineCfg.value.filter_operator = s.filter_operator || 'contains'
        pipelineCfg.value.filter_values = s.filter_values || []
        pipelineCfg.value.view_id = s.view_id || ''
        if (!pipelineCfg.value.table1_id && s.table_id) pipelineCfg.value.table1_id = s.table_id
      }
      if (s.step === 'feishu_push_json') {
        pipelineCfg.value.table2_id = s.table_id || ''
        pipelineCfg.value.json_columns = s.json_columns || ''
        pipelineCfg.value.json_primary = s.json_primary || '记录ID'
        pipelineCfg.value.range_start = s.range_start || null
        pipelineCfg.value.range_end = s.range_end || null
      }
    }
  }
  showCreate.value = true
}

async function updateTask() {
  if (!editingTaskId.value) return
  if (!newTask.value.name.trim()) { message.warning('请填写任务名称'); return }
  try {
    const scheduleConfig: any = {}
    if (newTask.value.schedule_type === 'interval') scheduleConfig.hours = intervalHours.value
    if (newTask.value.schedule_type === 'cron') scheduleConfig.cron = cronExpr.value

    // 构建 task_config（与 createTask 相同逻辑）
    let taskConfig: any = {}
    if (newTask.value.task_type === 'subscription_combo') {
      const cfg = pipelineCfg.value
      const pipeline: any[] = []
      const step1: any = { step: 'subscription_crawl', platform: newTask.value.platform }
      if (cfg.crawl_limit > 0) step1.limit = cfg.crawl_limit
      if (cfg.crawl_timeout !== 3600) step1.timeout_seconds = cfg.crawl_timeout
      pipeline.push(step1)
      const step2: any = { step: 'feishu_push', platform: newTask.value.platform, data_type: cfg.data_type }
      if (cfg.table1_id) step2.table_id = cfg.table1_id
      pipeline.push(step2)
      if (cfg.table1_id) {
        const step3: any = { step: 'feishu_pull', table_id: cfg.table1_id, platform: newTask.value.platform, output: 'step3_csv' }
        if (cfg.filter_field && cfg.filter_values.length) {
          step3.filter_field = cfg.filter_field; step3.filter_operator = cfg.filter_operator; step3.filter_values = cfg.filter_values
        }
        if (cfg.view_id) step3.view_id = cfg.view_id
        pipeline.push(step3)
      }
      if (cfg.table2_id && cfg.json_columns) {
        const step4: any = { step: 'feishu_push_json', input: 'step3_csv', table_id: cfg.table2_id, json_columns: cfg.json_columns, json_primary: cfg.json_primary || '记录ID' }
        if (cfg.range_start) step4.range_start = cfg.range_start
        if (cfg.range_end) step4.range_end = cfg.range_end
        pipeline.push(step4)
      }
      taskConfig = { pipeline }
    }

    await http.put(`/scheduler/tasks/${editingTaskId.value}`, {
      name: newTask.value.name,
      schedule_type: newTask.value.schedule_type,
      schedule_config: scheduleConfig,
      task_config: taskConfig,
    })
    message.success('任务更新成功')
    showCreate.value = false
    editingTaskId.value = null
    loadTasks()
    loadStatus()
  } catch (e: any) {
    message.error(e.message || '更新失败')
  }
}

async function triggerTask(id: number) {
  try {
    const { data } = await http.post(`/scheduler/tasks/${id}/trigger`)
    message.success(data.message || '任务已触发')
    loadExecutions()
  } catch (e: any) {
    message.error(e.message || '触发失败')
  }
}

async function toggleTask(row: any) {
  try {
    await http.put(`/scheduler/tasks/${row.id}`, { is_active: !row.is_active })
    message.success(row.is_active ? '已禁用' : '已启用')
    loadTasks()
  } catch (e: any) {
    message.error(e.message || '操作失败')
  }
}

async function deleteTask(id: number) {
  try {
    await http.delete(`/scheduler/tasks/${id}`)
    message.success('任务已删除')
    loadTasks()
    loadStatus()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

onMounted(() => {
  loadStatus()
  loadTasks()
  loadExecutions()
})
</script>
