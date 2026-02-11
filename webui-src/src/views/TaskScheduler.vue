<template>
  <div>
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

    <!-- Create Modal -->
    <n-modal v-model:show="showCreate" title="新建定时任务" preset="dialog" style="width: 520px">
      <n-form label-placement="left" label-width="100">
        <n-form-item label="任务名称">
          <n-input v-model:value="newTask.name" placeholder="例: 每日小红书采集" />
        </n-form-item>
        <n-form-item label="任务类型">
          <n-select v-model:value="newTask.task_type" :options="taskTypeOptions" />
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
      <template #action>
        <n-button @click="showCreate = false">取消</n-button>
        <n-button type="primary" @click="createTask">创建</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { NTag, NButton, NSpace, useMessage } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import http from '@/api'

const message = useMessage()
const loading = ref(false)
const execLoading = ref(false)
const showCreate = ref(false)

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
  { label: '清理', value: 'cleanup' },
]

const platformOptions = [
  { label: '小红书', value: 'xhs' },
  { label: '抖音', value: 'dy' },
  { label: 'B站', value: 'bili' },
  { label: '微博', value: 'wb' },
  { label: '微信', value: 'wechat' },
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
  {
    title: '操作', key: 'actions', width: 200,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => triggerTask(row.id) }, () => '执行'),
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
]

async function loadStatus() {
  try {
    const { data } = await http.get('/scheduler/status')
    schedulerStatus.value = data.data || {}
  } catch { /* silent */ }
}

async function loadTasks() {
  loading.value = true
  try {
    const { data } = await http.get('/scheduler/tasks')
    tasks.value = data.data?.items || []
  } catch (e: any) {
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
    executions.value = data.data?.items || []
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    execLoading.value = false
  }
}

async function createTask() {
  try {
    const scheduleConfig: any = {}
    if (newTask.value.schedule_type === 'interval') scheduleConfig.hours = intervalHours.value
    if (newTask.value.schedule_type === 'cron') scheduleConfig.cron = cronExpr.value

    await http.post('/scheduler/tasks', {
      ...newTask.value,
      schedule_config: scheduleConfig,
      task_config: {},
    })
    message.success('任务创建成功')
    showCreate.value = false
    loadTasks()
    loadStatus()
  } catch (e: any) {
    message.error(e.message || '创建失败')
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
