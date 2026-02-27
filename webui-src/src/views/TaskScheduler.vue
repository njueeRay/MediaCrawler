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
              <n-button type="primary" size="small" @click="openCreate()">新建任务</n-button>
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
    <n-modal v-model:show="showCreate" :title="editingTaskId ? '编辑定时任务' : '新建定时任务'" preset="dialog" style="width: 640px; max-height: 90vh; overflow-y: auto">
      <n-form label-placement="left" label-width="110">
        <n-form-item label="任务名称">
          <n-input v-model:value="newTask.name" placeholder="例: 每日微信采集" />
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
          <n-input v-model:value="cronExpr" placeholder="例: 0 14 * * *（每天14:00）" />
          <span class="ml-2 text-xs text-gray-400">分 时 日 月 周</span>
        </n-form-item>
      </n-form>

      <!-- ========== Pipeline 步骤配置 ========== -->
      <n-divider class="text-xs">Pipeline 步骤配置</n-divider>
      <n-alert type="info" class="mb-3" :bordered="false" style="font-size: 12px">
        根据任务类型自动预填步骤，可手动调整。所有任务最终以 Pipeline 方式执行。
      </n-alert>

      <!-- 步骤列表 -->
      <div v-for="(step, idx) in pipelineSteps" :key="idx" class="mb-3" style="border: 1px solid #e0e0e6; border-radius: 6px; padding: 12px;">
        <n-space align="center" class="mb-2">
          <n-tag size="small" :type="stepTagType(step.step) as any">步骤 {{ idx + 1 }}</n-tag>
          <n-select v-model:value="step.step" :options="availableStepOptions" style="width: 200px" size="small" @update:value="() => onStepTypeChange(idx)" />
          <n-button size="tiny" quaternary type="error" @click="removeStep(idx)" :disabled="pipelineSteps.length <= 1">删除</n-button>
        </n-space>

        <!-- subscription_crawl 配置 -->
        <template v-if="step.step === 'subscription_crawl'">
          <n-form label-placement="left" label-width="100" size="small">
            <n-form-item label="采集数量上限">
              <n-input-number v-model:value="step.limit" :min="0" placeholder="0=不限" style="width:140px" />
            </n-form-item>
            <n-form-item label="超时(秒)">
              <n-input-number v-model:value="step.timeout_seconds" :min="60" style="width:140px" />
            </n-form-item>
          </n-form>
        </template>

        <!-- crawl 配置 -->
        <template v-if="step.step === 'crawl'">
          <n-form label-placement="left" label-width="100" size="small">
            <n-form-item label="爬虫类型">
              <n-select v-model:value="step.crawler_type" :options="crawlerTypeOptions" style="width:140px" />
            </n-form-item>
            <n-form-item label="关键词" v-if="step.crawler_type === 'search'">
              <n-input v-model:value="step.keywords" placeholder="搜索关键词" />
            </n-form-item>
            <n-form-item label="创作者ID" v-if="step.crawler_type === 'creator'">
              <n-input v-model:value="step.creator_ids" placeholder="逗号分隔" />
            </n-form-item>
            <n-form-item label="超时(秒)">
              <n-input-number v-model:value="step.timeout_seconds" :min="60" style="width:140px" />
            </n-form-item>
          </n-form>
        </template>

        <!-- feishu_push 配置 -->
        <template v-if="step.step === 'feishu_push'">
          <n-form label-placement="left" label-width="100" size="small">
            <n-form-item label="数据类型">
              <n-select v-model:value="step.data_type" :options="dataTypeOptions" style="width:140px" />
            </n-form-item>
            <n-form-item label="目标表 ID">
              <n-input v-model:value="step.table_id" placeholder="tblXXXXXXX（不填读环境变量）" />
            </n-form-item>
          </n-form>
        </template>

        <!-- feishu_pull 配置 -->
        <template v-if="step.step === 'feishu_pull'">
          <n-form label-placement="left" label-width="100" size="small">
            <n-form-item label="来源表 ID" required>
              <n-input v-model:value="step.table_id" placeholder="tblXXXXXXX" />
            </n-form-item>
            <n-form-item label="过滤字段">
              <n-input v-model:value="step.filter_field" placeholder="例: 信息质量评估" />
            </n-form-item>
            <n-form-item label="过滤运算">
              <n-select v-model:value="step.filter_operator" :options="filterOps" style="width:140px" />
            </n-form-item>
            <n-form-item label="过滤值">
              <n-dynamic-tags v-model:value="step.filter_values" />
            </n-form-item>
            <n-form-item label="视图 ID">
              <n-input v-model:value="step.view_id" placeholder="可空" />
            </n-form-item>
          </n-form>
        </template>

        <!-- feishu_push_json 配置 -->
        <template v-if="step.step === 'feishu_push_json'">
          <n-form label-placement="left" label-width="100" size="small">
            <n-form-item label="目标表 ID" required>
              <n-input v-model:value="step.table_id" placeholder="tblYYYYYYY" />
            </n-form-item>
            <n-form-item label="JSON 列名" required>
              <n-input v-model:value="step.json_columns" placeholder="例: AI文本分析" />
            </n-form-item>
            <n-form-item label="主键列">
              <n-input v-model:value="step.json_primary" placeholder="默认: 记录ID" />
            </n-form-item>
            <n-form-item label="范围">
              <n-space>
                <n-input-number v-model:value="step.range_start" :min="1" placeholder="起始" style="width:100px" />
                <span>~</span>
                <n-input-number v-model:value="step.range_end" :min="1" placeholder="结束" style="width:100px" />
              </n-space>
            </n-form-item>
          </n-form>
        </template>
      </div>

      <n-button dashed block size="small" @click="addStep">+ 添加步骤</n-button>

      <template #action>
        <n-button @click="cancelCreate()">取消</n-button>
        <n-button type="primary" @click="editingTaskId ? updateTask() : createTask()">{{ editingTaskId ? '保存' : '创建' }}</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { NTag, NButton, NSpace, useMessage, useDialog, NLog } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import http, { isDbError, unwrapApiData } from '@/api'
import DbRequiredAlert from '@/components/common/DbRequiredAlert.vue'

const message = useMessage()
const dialog = useDialog()
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
  task_type: 'subscription_combo',
  platform: 'wechat',
  schedule_type: 'interval',
})

// Pipeline 步骤数组（解耦化核心）
const pipelineSteps = ref<any[]>([])

const taskTypeOptions = [
  { label: '仅采集（订阅）', value: 'subscription_crawl' },
  { label: '仅采集（搜索/指定）', value: 'crawl' },
  { label: '仅同步到飞书', value: 'sync' },
  { label: '全流程（采集+同步）', value: 'subscription_combo' },
]

const availableStepOptions = [
  { label: '订阅采集', value: 'subscription_crawl' },
  { label: '通用采集', value: 'crawl' },
  { label: '同步到飞书表', value: 'feishu_push' },
  { label: '从飞书表拉取', value: 'feishu_pull' },
  { label: 'JSON展开推送', value: 'feishu_push_json' },
]

const crawlerTypeOptions = [
  { label: '搜索', value: 'search' },
  { label: '创作者', value: 'creator' },
  { label: '详情', value: 'detail' },
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

const platformOptions = [
  { label: '微信', value: 'wechat' },
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
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

// ─── 步骤默认值工厂 ─────────────────────────────────────────────────────────

function createDefaultStep(stepType: string, platform?: string): any {
  const p = platform || newTask.value.platform || 'wechat'
  switch (stepType) {
    case 'subscription_crawl':
      return { step: 'subscription_crawl', platform: p, limit: 0, timeout_seconds: 3600 }
    case 'crawl':
      return { step: 'crawl', platform: p, crawler_type: 'search', keywords: '', creator_ids: '', timeout_seconds: 1800 }
    case 'feishu_push':
      return { step: 'feishu_push', platform: p, data_type: p === 'wechat' ? 'article' : 'note', table_id: '' }
    case 'feishu_pull':
      return { step: 'feishu_pull', platform: p, table_id: '', filter_field: '', filter_operator: 'contains', filter_values: [], view_id: '', output: 'step3_csv' }
    case 'feishu_push_json':
      return { step: 'feishu_push_json', input: 'step3_csv', table_id: '', json_columns: '', json_primary: '记录ID', range_start: null, range_end: null }
    default:
      return { step: stepType }
  }
}

function getDefaultPipeline(taskType: string, platform?: string): any[] {
  const p = platform || newTask.value.platform || 'wechat'
  switch (taskType) {
    case 'subscription_crawl':
      return [createDefaultStep('subscription_crawl', p)]
    case 'crawl':
      return [createDefaultStep('crawl', p)]
    case 'sync':
      return [createDefaultStep('feishu_push', p)]
    case 'subscription_combo':
      return [
        createDefaultStep('subscription_crawl', p),
        createDefaultStep('feishu_push', p),
        createDefaultStep('feishu_pull', p),
        createDefaultStep('feishu_push_json', p),
      ]
    default:
      return [createDefaultStep('subscription_crawl', p)]
  }
}

function stepTagType(stepType: string): string {
  const m: Record<string, string> = {
    subscription_crawl: 'info',
    crawl: 'info',
    feishu_push: 'success',
    feishu_pull: 'warning',
    feishu_push_json: 'error',
  }
  return (m[stepType] || 'default') as any
}

// ─── 步骤操作 ────────────────────────────────────────────────────────────────

function addStep() {
  pipelineSteps.value.push(createDefaultStep('feishu_push'))
}

function removeStep(idx: number) {
  pipelineSteps.value.splice(idx, 1)
}

function onStepTypeChange(idx: number) {
  const step = pipelineSteps.value[idx]
  const newStep = createDefaultStep(step.step)
  pipelineSteps.value[idx] = newStep
}

// ─── 表单操作 ────────────────────────────────────────────────────────────────

function resetFormState() {
  editingTaskId.value = null
  newTask.value = { name: '', task_type: 'subscription_combo', platform: 'wechat', schedule_type: 'interval' }
  intervalHours.value = 6
  cronExpr.value = ''
  pipelineSteps.value = getDefaultPipeline('subscription_combo', 'wechat')
}

function openCreate() {
  resetFormState()
  showCreate.value = true
}

function cancelCreate() {
  showCreate.value = false
  editingTaskId.value = null
}

function onTaskTypeChange(val: string) {
  if (val === 'subscription_combo' || val === 'subscription_crawl') {
    if (!newTask.value.platform) newTask.value.platform = 'wechat'
  }
  pipelineSteps.value = getDefaultPipeline(val, newTask.value.platform)
}

// ─── 从 pipeline 步骤数组构建 task_config ────────────────────────────────────

function buildTaskConfig(): any {
  const steps = pipelineSteps.value.map((s: any) => {
    const clean: any = { step: s.step }
    if (s.platform) clean.platform = s.platform

    if (s.step === 'subscription_crawl') {
      if (s.limit > 0) clean.limit = s.limit
      if (s.timeout_seconds && s.timeout_seconds !== 3600) clean.timeout_seconds = s.timeout_seconds
    }
    if (s.step === 'crawl') {
      clean.crawler_type = s.crawler_type || 'search'
      if (s.keywords) clean.keywords = s.keywords
      if (s.creator_ids) clean.creator_ids = s.creator_ids
      if (s.timeout_seconds && s.timeout_seconds !== 1800) clean.timeout_seconds = s.timeout_seconds
    }
    if (s.step === 'feishu_push') {
      if (s.data_type) clean.data_type = s.data_type
      if (s.table_id) clean.table_id = s.table_id
    }
    if (s.step === 'feishu_pull') {
      if (s.table_id) clean.table_id = s.table_id
      if (s.filter_field && s.filter_values?.length) {
        clean.filter_field = s.filter_field
        clean.filter_operator = s.filter_operator
        clean.filter_values = s.filter_values
      }
      if (s.view_id) clean.view_id = s.view_id
      if (s.output) clean.output = s.output
    }
    if (s.step === 'feishu_push_json') {
      if (s.input) clean.input = s.input
      if (s.table_id) clean.table_id = s.table_id
      if (s.json_columns) clean.json_columns = s.json_columns
      if (s.json_primary) clean.json_primary = s.json_primary
      if (s.range_start) clean.range_start = s.range_start
      if (s.range_end) clean.range_end = s.range_end
    }
    return clean
  })
  return { pipeline: steps }
}

// ─── 从 task_config 恢复 pipeline 步骤 ──────────────────────────────────────

function restorePipelineFromConfig(taskConfig: any, taskType: string, platform: string) {
  if (taskConfig?.pipeline && Array.isArray(taskConfig.pipeline) && taskConfig.pipeline.length > 0) {
    pipelineSteps.value = taskConfig.pipeline.map((s: any) => {
      const defaults = createDefaultStep(s.step, platform)
      return { ...defaults, ...s }
    })
  } else {
    pipelineSteps.value = getDefaultPipeline(taskType, platform)
  }
}

// ─── Task 表格列定义 ────────────────────────────────────────────────────────

const columns: DataTableColumn[] = [
  { title: '名称', key: 'name' },
  {
    title: '类型', key: 'task_type', width: 100,
    render: (row: any) => {
      const labels: Record<string, string> = {
        subscription_crawl: '订阅采集', crawl: '采集', sync: '同步',
        subscription_combo: '全流程', combo: '采集+同步', cleanup: '清理',
      }
      return h(NTag, { size: 'small' }, () => labels[row.task_type] || row.task_type)
    },
  },
  { title: '平台', key: 'platform', width: 80 },
  {
    title: '状态', key: 'is_active', width: 80,
    render: (row: any) => h(NTag, { size: 'small', type: row.is_active ? 'success' : 'default' }, () => row.is_active ? '启用' : '禁用'),
  },
  { title: '执行', key: 'run_count', width: 60 },
  { title: '失败', key: 'fail_count', width: 60 },
  { title: '上次执行', key: 'last_run_at', width: 160 },
  {
    title: '调度',
    key: 'schedule',
    width: 160,
    ellipsis: { tooltip: true },
    render: (row: any) => {
      if (!row.schedule_type) return '-'
      if (row.schedule_type === 'interval') {
        const hrs = row.schedule_config?.hours
        return `每 ${hrs || '-'} 小时`
      }
      if (row.schedule_type === 'cron') {
        return row.schedule_config?.cron || 'cron'
      }
      return row.schedule_type
    },
  },
  {
    title: '操作', key: 'actions', width: 300,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => triggerTask(row) }, () => '执行'),
        h(NButton, { size: 'tiny', type: 'info', onClick: () => openEdit(row) }, () => '编辑'),
        h(NButton, { size: 'tiny', onClick: () => toggleTask(row) }, () => row.is_active ? '禁用' : '启用'),
        h(NButton, { size: 'tiny', type: 'error', onClick: () => deleteTask(row.id) }, () => '删除'),
      ]),
  },
]

const execColumns: DataTableColumn[] = [
  { title: '任务', key: 'task_name', width: 160 },
  {
    title: '触发', key: 'trigger_type', width: 60,
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
  { title: '耗时(秒)', key: 'duration_seconds', width: 80 },
  { title: '错误', key: 'error_message', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', onClick: () => openExecutionLog(row.id) }, () => '日志'),
        row.status === 'running'
          ? h(NButton, { size: 'tiny', type: 'error', onClick: () => abortExecution(row.id) }, () => '中断')
          : null,
      ]),
  },
]

// ─── API 调用 ────────────────────────────────────────────────────────────────

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

    const taskConfig = buildTaskConfig()

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
    message.error(e.response?.data?.detail || e.message || '创建失败（任务名称可能已存在）')
  }
}

async function openEdit(row: any) {
  editingTaskId.value = row.id

  newTask.value = {
    name: row.name || '',
    task_type: row.task_type || 'subscription_combo',
    platform: row.platform || 'wechat',
    schedule_type: row.schedule_type || 'interval',
  }
  if (row.schedule_type === 'interval') {
    intervalHours.value = row.schedule_config?.hours || 6
  } else if (row.schedule_type === 'cron') {
    cronExpr.value = row.schedule_config?.cron || ''
  }

  // P0-2 FIX: 加载完整 task_config（列表 API 现已返回，但双重保障）
  let taskConfig = row.task_config
  if (!taskConfig || Object.keys(taskConfig).length === 0) {
    try {
      const { data } = await http.get(`/scheduler/tasks/${row.id}`)
      const detail = unwrapApiData<any>(data) || {}
      taskConfig = detail.task_config || {}
    } catch (e: any) {
      message.warning('加载任务详情失败，使用默认配置')
      taskConfig = {}
    }
  }

  restorePipelineFromConfig(taskConfig, newTask.value.task_type, newTask.value.platform)
  showCreate.value = true
}

async function updateTask() {
  if (!editingTaskId.value) return
  if (!newTask.value.name.trim()) { message.warning('请填写任务名称'); return }
  if (newTask.value.schedule_type === 'cron' && !cronExpr.value.trim()) { message.warning('请填写 Cron 表达式'); return }
  try {
    const scheduleConfig: any = {}
    if (newTask.value.schedule_type === 'interval') scheduleConfig.hours = intervalHours.value
    if (newTask.value.schedule_type === 'cron') scheduleConfig.cron = cronExpr.value

    const taskConfig = buildTaskConfig()

    // P0-1 FIX: 发送完整字段（包含 task_type / platform / task_config）
    await http.put(`/scheduler/tasks/${editingTaskId.value}`, {
      name: newTask.value.name,
      task_type: newTask.value.task_type,
      platform: newTask.value.platform,
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
    message.error(e.response?.data?.detail || e.message || '更新失败')
  }
}

async function triggerTask(row: any) {
  // P1-4: 禁用任务手动执行需确认
  if (!row.is_active) {
    dialog.warning({
      title: '任务已禁用',
      content: '该任务当前处于禁用状态（不会定时执行）。确认手动触发一次？',
      positiveText: '确认执行',
      negativeText: '取消',
      onPositiveClick: async () => {
        await doTriggerTask(row.id)
      },
    })
    return
  }
  await doTriggerTask(row.id)
}

async function doTriggerTask(id: number) {
  try {
    const { data } = await http.post(`/scheduler/tasks/${id}/trigger`)
    message.success(data.message || '任务已触发')
    loadExecutions()
  } catch (e: any) {
    message.error(e.message || '触发失败')
  }
}

async function abortExecution(executionId: number) {
  try {
    const { data } = await http.post(`/scheduler/executions/${executionId}/abort`)
    message.success(data.message || '中断指令已发送')
    loadExecutions()
  } catch (e: any) {
    message.error(e.message || '中断失败')
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
