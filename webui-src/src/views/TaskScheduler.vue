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
        <n-card size="small" title="定时任务列表">
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
        <n-space v-if="_isPolling" align="center" :size="6" class="mt-1">
          <n-spin size="small" />
          <span class="text-xs" style="color: #2080f0">实时轮询中，每 2 秒刷新…</span>
        </n-space>
        <n-log ref="logRef" :log="execLogText" language="text" :rows="22" />
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
          <n-select v-model:value="newTask.platform" :options="platformOptions" clearable @update:value="onPlatformChange" />
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
          <n-form label-placement="left" label-width="110" size="small">
            <n-form-item label="指定采集账号">
              <n-select
                v-model:value="step.only_creator_ids"
                :options="subscriptionOptions"
                :loading="subscriptionLoading"
                multiple
                filterable
                clearable
                placeholder="不选则采集全部活跃订阅"
                style="width: 100%"
              />
            </n-form-item>
            <n-form-item label="采集数量上限">
              <n-input-number v-model:value="step.limit" :min="0" placeholder="0=不限" style="width:140px" />
              <span class="ml-2 text-xs text-gray-400">0 = 不限</span>
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
            <n-form-item label="失败重试">
              <n-input-number v-model:value="step.retry_count" :min="0" :max="5" style="width:100px" />
              <span class="ml-2 text-xs text-gray-400">次（XHS/抖音建议 2）</span>
            </n-form-item>
          </n-form>
        </template>

        <!-- multi_platform_crawl 配置 -->
        <template v-if="step.step === 'multi_platform_crawl'">
          <n-form label-placement="left" label-width="120" size="small">
            <n-form-item label="采集平台">
              <n-select
                v-model:value="step.platforms"
                :options="platformOptions"
                multiple
                placeholder="选择一个或多个平台"
                style="min-width:280px"
              />
            </n-form-item>
            <n-form-item label="每平台数量上限">
              <n-input-number v-model:value="step.limit_per_platform" :min="0" placeholder="0=不限" style="width:140px" />
            </n-form-item>
            <n-form-item label="某平台失败时">
              <n-switch v-model:value="step.stop_on_failure" />
              <span class="ml-2 text-xs text-gray-400">{{ step.stop_on_failure ? '中止全部' : '跳过继续' }}</span>
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
              <n-select
                v-if="_fieldCacheState[step.table_id]?.length"
                v-model:value="step.filter_field"
                :options="_fieldCacheState[step.table_id]"
                :loading="!!_fieldLoading[step.table_id]"
                filterable clearable
                placeholder="选择过滤字段"
                style="width:100%"
              />
              <n-input
                v-else
                v-model:value="step.filter_field"
                :loading="!!_fieldLoading[step.table_id]"
                placeholder="填写字段名，或先填写表 ID 加载字段列表"
              />
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
            <n-form-item label="过滤逻辑">
              <n-select v-model:value="step.filter_conjunction" :options="conjunctionOps" style="width:180px" />
              <n-text depth="3" style="font-size:11px;margin-left:8px">多个过滤值之间的逻辑关系（默认 AND）</n-text>
            </n-form-item>
            <n-form-item label="输出格式">
              <n-select v-model:value="step.output_format" :options="outputFormatOps" style="width:210px" />
            </n-form-item>
            <n-form-item label="输出变量名" required>
              <div style="width:100%">
                <n-input v-model:value="step.output" placeholder="feishu_pull_result" />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">下游 feishu_push_json / feishu_update_records 通过此名称引用本步骤数据</n-text>
              </div>
            </n-form-item>
          </n-form>
        </template>

        <!-- feishu_push_json 配置 -->
        <template v-if="step.step === 'feishu_push_json'">
          <n-form label-placement="left" label-width="100" size="small">
            <n-form-item label="输入引用" required>
              <div style="width:100%">
                <n-select
                  v-if="getUpstreamOutputKeys(idx).length"
                  v-model:value="step.input"
                  :options="getUpstreamOutputKeys(idx)"
                  filterable
                  placeholder="选择上游 feishu_pull 的输出变量名"
                />
                <n-input v-else v-model:value="step.input" placeholder="feishu_pull_result" />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">对应上游 feishu_pull 步骤设置的"输出变量名"</n-text>
              </div>
            </n-form-item>
            <n-form-item label="目标表 ID" required>
              <n-input v-model:value="step.table_id" placeholder="tblYYYYYYY" />
            </n-form-item>
            <n-form-item label="JSON 列名" required>
              <n-select
                :value="step.json_columns ? step.json_columns.split(',').map((c:string)=>c.trim()).filter(Boolean) : []"
                @update:value="(v: string[]) => step.json_columns = v.join(',')"
                multiple filterable tag
                placeholder="输入本地数据的 JSON 列名，回车确认（如 AI文本分析）"
                style="width:100%"
              />
              <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">指本地数据集中内容为 JSON 字符串的列名，与目标飞书表列名无关</n-text>
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

        <!-- feishu_update_records 配置 -->
        <template v-if="step.step === 'feishu_update_records'">
          <n-form label-placement="left" label-width="110" size="small">
            <n-form-item label="目标表 ID" required>
              <n-input v-model:value="step.table_id" placeholder="tblXXXXXXX（通常与 feishu_pull 相同）" />
            </n-form-item>
            <n-form-item label="输入引用" required>
              <div style="width:100%">
                <n-select
                  v-if="getUpstreamOutputKeys(idx).length"
                  v-model:value="step.input"
                  :options="getUpstreamOutputKeys(idx)"
                  filterable
                  placeholder="选择上游 feishu_pull 的输出变量名"
                />
                <n-input v-else v-model:value="step.input" placeholder="feishu_pull_result" />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">请选择上游 feishu_pull 步骤的输出变量名（未设置时手动填写）</n-text>
              </div>
            </n-form-item>
            <n-form-item label="回写字段" required>
              <div style="width:100%">
                <div v-for="(pair, pi) in (step._kv_pairs || [])" :key="pi" style="display:flex;gap:6px;margin-bottom:4px;align-items:center">
                  <n-select
                    v-if="_fieldCacheState[step.table_id]?.length"
                    :value="pair.key"
                    @update:value="(v: string) => { pair.key = v }"
                    :options="_fieldCacheState[step.table_id]"
                    filterable
                    clearable
                    placeholder="字段名"
                    style="flex:2;min-width:0"
                    size="small"
                  />
                  <n-input
                    v-else
                    v-model:value="pair.key"
                    placeholder="字段名"
                    style="flex:2;min-width:0"
                    size="small"
                  />
                  <n-input
                    v-model:value="pair.value"
                    placeholder="值（true/false/now/文本/数字）"
                    style="flex:3;min-width:0"
                    size="small"
                  />
                  <n-button size="tiny" quaternary type="error" @click="step._kv_pairs.splice(pi, 1)">×</n-button>
                </div>
                <n-button dashed size="small" block style="margin-top:4px" @click="(step._kv_pairs = step._kv_pairs || []).push({ key: '', value: '' })">+ 添加字段</n-button>
                <n-text depth="3" style="font-size:11px;margin-top:2px;display:block">支持魔法值："now" → 当前毫秒时间戳；true / false → 复选框布尔值</n-text>
              </div>
            </n-form-item>
            <n-form-item label="出错时跳过">
              <n-switch v-model:value="step.skip_on_error" />
              <span class="ml-2 text-xs text-gray-400">{{ step.skip_on_error ? '单批失败后继续' : '首批失败即中止' }}</span>
            </n-form-item>
            <n-form-item label="试运行">
              <n-switch v-model:value="step.dry_run" />
              <span class="ml-2 text-xs text-gray-400">开启后只打印 record_ids，不写入飞书</span>
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
import { ref, h, onMounted, watch, nextTick, watchEffect } from 'vue'
import { NTag, NButton, NSpace, useMessage, useDialog, NLog, NSpin } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import { useRoute } from 'vue-router'
import http, { isDbError, unwrapApiData } from '@/api'
import DbRequiredAlert from '@/components/common/DbRequiredAlert.vue'

const message = useMessage()
const dialog = useDialog()
const route = useRoute()
const loading = ref(false)
const execLoading = ref(false)
const showCreate = ref(false)
const editingTaskId = ref<number | null>(null)
const dbNotReady = ref(false)
const showExecLog = ref(false)
const execLogText = ref('')
const execLogMeta = ref<{ execution_id?: number; status?: string; started_at?: string; finished_at?: string }>({})
const logRef = ref<any>(null)
const _isPolling = ref(false)
let _logPollTimer: ReturnType<typeof setInterval> | null = null

// 遗书字段缓存（会话级，刷新后清空）
/** 飞书字段类型 int -> 中文标签 */
const FEISHU_FIELD_TYPE_LABELS: Record<number, string> = {
  1: '文本', 2: '数字', 3: '单选', 4: '多选', 5: '日期',
  7: '复选框', 11: '人员', 13: '电话', 15: '超链接', 17: '附件',
  18: '关联', 19: '公式', 20: '自动编号',
}
interface FieldOption { label: string; value: string; type: number }
/** key=table_id → 字段选项列表（响应式） */
const _fieldCacheState = ref<Record<string, FieldOption[]>>({})
/** key=table_id → 是否加载中 */
const _fieldLoading = ref<Record<string, boolean>>({})

function _stopLogPoll() {
  if (_logPollTimer !== null) {
    clearInterval(_logPollTimer)
    _logPollTimer = null
    _isPolling.value = false
  }
}

// 关闭日志弹窗时自动停止轮询
watch(showExecLog, (val) => { if (!val) _stopLogPoll() })

// 字段加载：按 table_id 向后端请求飞书字段列表（自动去重，会话级缓存）
async function loadFields(tableId: string): Promise<void> {
  if (!tableId || !tableId.startsWith('tbl') || tableId.length <= 6) return
  if (_fieldCacheState.value[tableId] || _fieldLoading.value[tableId]) return
  _fieldLoading.value = { ..._fieldLoading.value, [tableId]: true }
  try {
    const res = await http.get(`/feishu/tables/${tableId}/fields`)
    const data: Array<{ field_name: string; type: number }> = unwrapApiData(res.data) || []
    _fieldCacheState.value = {
      ..._fieldCacheState.value,
      [tableId]: data.map(f => ({
        label: `${f.field_name}\uff08${FEISHU_FIELD_TYPE_LABELS[f.type] ?? '\u672a\u77e5'}\uff09`,
        value: f.field_name,
        type: f.type,
      })),
    }
  } catch (e: any) {
    message.warning(`\u5b57\u6bb5\u52a0\u8f7d\u5931\u8d25\uff1a${e?.message ?? '\u672a\u77e5\u9519\u8bef'}`)
  } finally {
    const tmp = { ..._fieldLoading.value }
    delete tmp[tableId]
    _fieldLoading.value = tmp
  }
}

// watchEffect \u76d1\u542c\u6240\u6709\u6b65\u9aa4\u7684 table_id \u53d8\u5316\uff0c\u81ea\u52a8\u52a0\u8f7d\u5b57\u6bb5\uff08\u907f\u514d\u5220\u9664\u6b65\u9aa4\u65f6 index \u9519\u4f4d\uff09
// Pipeline 步骤数组（解耦化核心）
const pipelineSteps = ref<any[]>([])

watchEffect(() => {
  for (const step of pipelineSteps.value) {
    if (['feishu_pull', 'feishu_update_records'].includes(step.step)) {
      const tid = step.table_id as string | undefined
      if (tid && tid.startsWith('tbl') && tid.length > 6 && !_fieldCacheState.value[tid]) {
        void loadFields(tid)
      }
    }
  }
})

// 日志内容更新时自动滚动到底部
watch(execLogText, async () => {
  await nextTick()
  logRef.value?.scrollTo({ position: 'bottom' })
})

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

// 订阅账号列表（供步骤表单选择）
const subscriptionOptions = ref<{ label: string; value: string }[]>([])
const subscriptionLoading = ref(false)

const taskTypeOptions = [
  { label: '仅采集（订阅）', value: 'subscription_crawl' },
  { label: '仅采集（搜索/指定）', value: 'crawl' },
  { label: '多平台订阅采集', value: 'multi_platform_crawl' },
  { label: '仅同步到飞书', value: 'sync' },
  { label: '全流程（采集+同步）', value: 'subscription_combo' },
]

const availableStepOptions = [
  { label: '订阅采集', value: 'subscription_crawl' },
  { label: '多平台订阅采集', value: 'multi_platform_crawl' },
  { label: '通用采集', value: 'crawl' },
  { label: '同步到飞书表', value: 'feishu_push' },
  { label: '从飞书表拉取', value: 'feishu_pull' },
  { label: 'JSON展开推送', value: 'feishu_push_json' },
  { label: '回写记录字段', value: 'feishu_update_records' },
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

const conjunctionOps = [
  { label: 'AND（全部匹配）', value: 'and' },
  { label: 'OR（任意匹配）', value: 'or' },
]
const outputFormatOps = [
  { label: 'SQLite（推荐，支持回写）', value: 'sqlite' },
  { label: 'CSV', value: 'csv' },
  { label: '两者都输出', value: 'both' },
]
/** 获取 stepIdx 之前所有 feishu_pull 步骤已设置的 output key，供下游选择 */
function getUpstreamOutputKeys(stepIdx: number): Array<{ label: string; value: string }> {
  return pipelineSteps.value
    .slice(0, stepIdx)
    .filter((s: any) => s.step === 'feishu_pull' && s.output)
    .map((s: any) => ({ label: `${s.output}  ←  feishu_pull`, value: s.output }))
}

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

// ─── 平台元数据 ─────────────────────────────────────────────────────────────

/** 各平台推送飞书时的默认 data_type（与 pipeline_steps.py PLATFORM_DATA_TYPES 保持同步） */
const PLATFORM_DATA_TYPES: Record<string, string> = {
  wechat: 'article',
  xhs:    'note',
  dy:     'video',
  bili:   'video',
  wb:     'weibo',
  ks:     'video',
  tieba:  'note',
  zhihu:  'note',
}

/** 需要 Playwright 的平台 */
const PLAYWRIGHT_PLATFORMS = new Set(['xhs', 'dy', 'bili', 'wb', 'ks', 'tieba', 'zhihu'])

// ─── 步骤默认值工厂 ─────────────────────────────────────────────────────────

function createDefaultStep(stepType: string, platform?: string): any {
  const p = platform || newTask.value.platform || 'wechat'
  const dataType = PLATFORM_DATA_TYPES[p] || 'note'
  const needRetry = PLAYWRIGHT_PLATFORMS.has(p)
  switch (stepType) {
    case 'subscription_crawl':
      return { step: 'subscription_crawl', platform: p, limit: 0, timeout_seconds: p === 'xhs' || p === 'dy' ? 2700 : 3600, only_creator_ids: [] }
    case 'crawl':
      return {
        step: 'crawl', platform: p,
        crawler_type: 'search', keywords: '', creator_ids: '',
        timeout_seconds: p === 'xhs' || p === 'dy' ? 2700 : 1800,
        retry_count: needRetry ? 2 : 0,
        retry_delay: 30,
      }
    case 'feishu_push':
      return { step: 'feishu_push', platform: p, data_type: dataType, table_id: '' }
    case 'feishu_pull':
      return { step: 'feishu_pull', platform: p, table_id: '', filter_field: '', filter_operator: 'contains', filter_values: [], view_id: '', filter_conjunction: 'and', output_format: 'sqlite', output: 'feishu_pull_result' }
    case 'feishu_push_json':
      return { step: 'feishu_push_json', input: 'feishu_pull_result', table_id: '', json_columns: '', json_primary: '记录ID', range_start: null, range_end: null }
    case 'feishu_update_records':
      return { step: 'feishu_update_records', table_id: '', input: 'feishu_pull_result', _kv_pairs: [{ key: '已入库', value: 'true' }, { key: '入库时间', value: 'now' }], skip_on_error: true, dry_run: false }
    case 'multi_platform_crawl':
      return { step: 'multi_platform_crawl', platforms: ['wechat', 'xhs'], limit_per_platform: 0, stop_on_failure: false }
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
    case 'multi_platform_crawl':
      return [
        createDefaultStep('multi_platform_crawl', p),
        createDefaultStep('feishu_push', p),
      ]
    case 'pull_update':
      return [
        createDefaultStep('feishu_pull', p),
        createDefaultStep('feishu_update_records', p),
      ]
    default:
      return [createDefaultStep('subscription_crawl', p)]
  }
}

function stepTagType(stepType: string): string {
  const m: Record<string, string> = {
    subscription_crawl:   'info',
    crawl:                'info',
    multi_platform_crawl: 'primary',
    feishu_push:          'success',
    feishu_pull:          'warning',
    feishu_push_json:     'error',
    feishu_update_records: 'primary',
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
  loadSubscriptions(newTask.value.platform)
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
  loadSubscriptions(newTask.value.platform)
}

function onPlatformChange(val: string) {
  pipelineSteps.value = getDefaultPipeline(newTask.value.task_type, val)
  loadSubscriptions(val)
}

// ─── 从 pipeline 步骤数组构建 task_config ────────────────────────────────────

function buildTaskConfig(): any {
  const steps = pipelineSteps.value.map((s: any) => {
    const clean: any = { step: s.step }
    if (s.platform) clean.platform = s.platform

    if (s.step === 'subscription_crawl') {
      if (s.limit > 0) clean.limit = s.limit
      if (s.timeout_seconds && s.timeout_seconds !== 3600) clean.timeout_seconds = s.timeout_seconds
      if (s.only_creator_ids && s.only_creator_ids.length > 0) clean.only_creator_ids = s.only_creator_ids
    }
    if (s.step === 'crawl') {
      clean.crawler_type = s.crawler_type || 'search'
      if (s.keywords) clean.keywords = s.keywords
      if (s.creator_ids) clean.creator_ids = s.creator_ids
      if (s.timeout_seconds && s.timeout_seconds !== 1800) clean.timeout_seconds = s.timeout_seconds
      if (s.retry_count && Number(s.retry_count) > 0) clean.retry_count = Number(s.retry_count)
      if (s.retry_delay && Number(s.retry_delay) !== 30) clean.retry_delay = Number(s.retry_delay)
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
    if (s.step === 'feishu_update_records') {
      if (s.table_id) clean.table_id = s.table_id
      if (s.input) clean.input = s.input
      const pairs: Array<{key: string; value: string}> = s._kv_pairs || []
      const fieldsToSet: Record<string, any> = {}
      for (const pair of pairs) {
        if (!pair.key) continue
        const v = pair.value
        if (v === 'true') fieldsToSet[pair.key] = true
        else if (v === 'false') fieldsToSet[pair.key] = false
        else if (v === 'now') fieldsToSet[pair.key] = 'now'
        else if (v !== '' && !isNaN(Number(v))) fieldsToSet[pair.key] = Number(v)
        else fieldsToSet[pair.key] = v
      }
      if (Object.keys(fieldsToSet).length === 0) throw new Error('步骤 feishu_update_records 的"回写字段"不能为空')
      clean.fields_to_set = fieldsToSet
      clean.skip_on_error = s.skip_on_error !== false
      if (s.dry_run) clean.dry_run = true
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
      const merged = { ...defaults, ...s }
      // feishu_update_records: fields_to_set dict → _kv_pairs array
      if (s.step === 'feishu_update_records' && s.fields_to_set && typeof s.fields_to_set === 'object') {
        merged._kv_pairs = Object.entries(s.fields_to_set).map(([k, v]: [string, any]) => ({
          key: k,
          value: v === true ? 'true' : v === false ? 'false' : String(v),
        }))
      }
      return merged
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
        subscription_crawl:   '订阅采集',
        crawl:                '采集',
        sync:                 '同步',
        multi_platform_crawl: '多平台',
        subscription_combo:   '全流程',
        combo: '采集+同步', cleanup: '清理',
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

async function _fetchExecLog(executionId: number): Promise<string | null> {
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
    return payload.status || null
  } catch (e: any) {
    execLogText.value = `加载失败: ${e.message || e}`
    return null
  }
}

async function openExecutionLog(executionId: number) {
  _stopLogPoll()
  execLogText.value = ''
  execLogMeta.value = { execution_id: executionId }
  showExecLog.value = true
  const status = await _fetchExecLog(executionId)
  // 任务运行中：开启轮询，每 2 秒刷新一次，直到任务结束或弹窗关闭
  if (status === 'running') {
    _isPolling.value = true
    _logPollTimer = setInterval(async () => {
      if (!showExecLog.value) { _stopLogPoll(); return }
      const s = await _fetchExecLog(executionId)
      if (s && s !== 'running') _stopLogPoll()
    }, 2000)
  }
}

async function loadSubscriptions(platform?: string) {
  subscriptionLoading.value = true
  try {
    const params: any = { size: 100, is_active: true }
    if (platform) params.platform = platform
    const { data } = await http.get('/subscribe', { params })
    const payload = unwrapApiData<any>(data) || {}
    subscriptionOptions.value = (payload.items || []).map((s: any) => ({
      label: s.creator_name ? `${s.creator_name}（${s.creator_id}）` : s.creator_id,
      value: s.creator_id,
    }))
  } catch {
    subscriptionOptions.value = []
  } finally {
    subscriptionLoading.value = false
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

    let taskConfig: any
    try { taskConfig = buildTaskConfig() } catch (e: any) { message.error(e.message || '配置错误'); return }

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
  loadSubscriptions(newTask.value.platform)
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

    let taskConfig: any
    try { taskConfig = buildTaskConfig() } catch (e: any) { message.error(e.message || '配置错误'); return }

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
    // 触发成功后自动打开日志弹窗
    const execId = data?.data?.execution_id
    if (execId) openExecutionLog(execId)
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

  // Handle preset query params when navigated from Subscription page
  const { preset_platform, preset_type, preset_name } = route.query
  if (preset_platform || preset_type) {
    resetFormState()
    if (preset_platform) newTask.value.platform = preset_platform as string
    if (preset_type) {
      newTask.value.task_type = preset_type as string
      pipelineSteps.value = getDefaultPipeline(preset_type as string, preset_platform as string || '')
    }
    if (preset_name) newTask.value.name = preset_name as string
    showCreate.value = true
  }
})
</script>
