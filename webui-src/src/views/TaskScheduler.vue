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
              <n-button size="small" type="warning" @click="cleanupExecutions">清理旧记录</n-button>
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
    <n-modal v-model:show="showExecLog" :title="execLogMeta.is_dry_run ? '[试运行] 日志' : '执行日志'" preset="dialog" style="width: 900px">
      <n-space vertical :size="10">
        <div class="text-xs text-gray-500">
          <span v-if="execLogMeta.execution_id">执行ID: {{ execLogMeta.execution_id }}</span>
          <span v-if="execLogMeta.status" class="ml-3">状态: {{ execLogMeta.status }}</span>
          <span v-if="execLogMeta.started_at" class="ml-3">开始: {{ execLogMeta.started_at }}</span>
          <span v-if="execLogMeta.finished_at" class="ml-3">结束: {{ execLogMeta.finished_at }}</span>
          <span v-if="execLogMeta.duration_seconds != null" class="ml-3">耗时: {{ execLogMeta.duration_seconds }}s</span>
        </div>
        <!-- 步骤状态指示行 -->
        <div v-if="execLogMeta.pipeline_steps && execLogMeta.pipeline_steps.length" style="display:flex;flex-wrap:wrap;gap:6px;padding:6px 0">
          <n-tag
            v-for="(sr, si) in execLogMeta.pipeline_steps"
            :key="si"
            :type="sr.status === 'ok' ? 'success' : sr.status === 'dry_run' ? 'info' : sr.status === 'skipped' ? 'warning' : 'error'"
            size="small"
            round
          >
            {{ si + 1 }}. {{ sr.step }}
            <template v-if="sr.status === 'ok'">✓</template>
            <template v-else-if="sr.status === 'dry_run'">~</template>
            <template v-else-if="sr.status === 'skipped'">⏭</template>
            <template v-else>✗</template>
            <template v-if="sr.duration_s != null">&nbsp;{{ sr.duration_s }}s</template>
          </n-tag>
        </div>
        <!-- M-2: 试运行报告 -->
        <n-alert
          v-if="execLogMeta.dry_run_report && execLogMeta.dry_run_report.length"
          type="info" :bordered="false" class="mt-1"
          title="试运行预览（未执行任何飞书写入）"
        >
          <p
            v-for="(line, li) in execLogMeta.dry_run_report" :key="li"
            style="margin:2px 0;font-size:12px;font-family:monospace"
          >{{ line }}</p>
        </n-alert>
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
        <n-form-item label="调度方式">
          <n-select v-model:value="schedulePreset" :options="schedulePresetOptions" style="width:220px" />
        </n-form-item>
        <!-- 每天：固定时间 -->
        <n-form-item label="执行时间" v-if="schedulePreset === 'daily'">
          <n-space align="center" :size="4">
            <n-select v-model:value="dailyTime.hour" :options="hourOptions" style="width:90px" />
            <span class="text-gray-400">时</span>
            <n-select v-model:value="dailyTime.minute" :options="minuteOptions" style="width:80px" />
            <span class="text-gray-400">分</span>
          </n-space>
        </n-form-item>
        <!-- 每周：指定星期+时间 -->
        <template v-if="schedulePreset === 'weekly'">
          <n-form-item label="星期">
            <n-select v-model:value="weeklyDays" :options="weekdayOptions" multiple style="width:300px" placeholder="选择星期（可多选）" />
          </n-form-item>
          <n-form-item label="执行时间">
            <n-space align="center" :size="4">
              <n-select v-model:value="weeklyTime.hour" :options="hourOptions" style="width:90px" />
              <span class="text-gray-400">时</span>
              <n-select v-model:value="weeklyTime.minute" :options="minuteOptions" style="width:80px" />
              <span class="text-gray-400">分</span>
            </n-space>
          </n-form-item>
        </template>
        <!-- 每隔N小时 -->
        <n-form-item label="间隔(小时)" v-if="schedulePreset === 'hourly'">
          <n-input-number v-model:value="intervalHours" :min="1" :max="168" />
        </n-form-item>
        <!-- 自定义 Cron -->
        <n-form-item label="Cron表达式" v-if="schedulePreset === 'custom'">
          <n-input v-model:value="cronExpr" placeholder="例: 0 14 * * *（每天14:00）" style="width:220px" />
          <span class="ml-2 text-xs text-gray-400">分 时 日 月 周</span>
        </n-form-item>
        <!-- 执行一次 -->
        <n-form-item label="执行时间" v-if="schedulePreset === 'once'">
          <n-input v-model:value="onceRunAt" placeholder="2026-06-01T09:00:00" style="width:220px" />
          <span class="ml-2 text-xs text-gray-400">ISO 格式日期时间</span>
        </n-form-item>
      </n-form>

      <!-- ========== Pipeline 步骤配置 ========== -->
      <n-divider class="text-xs">Pipeline 步骤配置</n-divider>
      <n-alert type="info" class="mb-3" :bordered="false" style="font-size: 12px">
        根据任务类型自动预填步骤，可手动调整。所有任务最终以 Pipeline 方式执行。
      </n-alert>

      <!-- 步骤列表 -->
      <template v-for="(step, idx) in pipelineSteps" :key="idx">
      <div class="mb-2" style="border: 1px solid #e0e0e6; border-radius: 6px; padding: 12px;">
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
            <n-form-item label="内容日期范围">
              <n-space vertical :size="4">
                <n-select v-model:value="step.date_range_type" :options="dateRangeOptions" style="width:220px" />
                <span class="text-xs text-gray-400">只采集该时段内发布的内容（微信已支持；其他平台陆续适配）</span>
              </n-space>
            </n-form-item>
            <template v-if="step.date_range_type === 'custom'">
              <n-form-item label="开始日期">
                <n-date-picker v-model:formatted-value="step.date_range_start" type="date" value-format="yyyy-MM-dd" clearable style="width:165px" />
              </n-form-item>
              <n-form-item label="结束日期">
                <n-date-picker v-model:formatted-value="step.date_range_end" type="date" value-format="yyyy-MM-dd" clearable style="width:165px" />
              </n-form-item>
            </template>
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
            <n-form-item label="数量上限">
              <n-input-number v-model:value="step.limit" :min="0" placeholder="0=不限" style="width:140px" />
            </n-form-item>
            <n-form-item label="超时(秒)">
              <n-input-number v-model:value="step.timeout_seconds" :min="60" style="width:140px" />
            </n-form-item>
            <n-form-item label="失败重试">
              <n-input-number v-model:value="step.retry_count" :min="0" :max="5" style="width:100px" />
              <span class="ml-2 text-xs text-gray-400">次（XHS/抖音建议 2）</span>
            </n-form-item>
            <n-form-item label="内容日期范围">
              <n-space vertical :size="4">
                <n-select v-model:value="step.date_range_type" :options="dateRangeOptions" style="width:220px" />
                <span class="text-xs text-gray-400">只采集该时段内发布的内容（微信已支持；其他平台陆续适配）</span>
              </n-space>
            </n-form-item>
            <template v-if="step.date_range_type === 'custom'">
              <n-form-item label="开始日期">
                <n-date-picker v-model:formatted-value="step.date_range_start" type="date" value-format="yyyy-MM-dd" clearable style="width:165px" />
              </n-form-item>
              <n-form-item label="结束日期">
                <n-date-picker v-model:formatted-value="step.date_range_end" type="date" value-format="yyyy-MM-dd" clearable style="width:165px" />
              </n-form-item>
            </template>
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
          <n-form label-placement="left" label-width="110" size="small">
            <n-form-item>
              <template #label>
                <span>数据表类型</span>
                <n-tooltip placement="right" trigger="hover" style="max-width:280px">
                  <template #trigger>
                    <n-icon class="ml-1 cursor-pointer" style="font-size:13px;color:#aaa;vertical-align:-2px">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
                    </n-icon>
                  </template>
                  <div style="font-size:12px;line-height:1.9">
                    <b>系统已根据平台自动匹配，一般无需修改：</b><br/>
                    • 微信公众号 → 文章 (article)<br/>
                    • 小红书/抖音/B站/微博 → 笔记/视频 (note)<br/>
                    • 创作者爬取模式 → 账号信息 (creator)
                  </div>
                </n-tooltip>
              </template>
              <n-select v-model:value="step.data_type" :options="dataTypeOptions" style="width:260px" />
            </n-form-item>
            <n-form-item label="目标表 ID">
              <n-input v-model:value="step.table_id" placeholder="tblXXXXXXX（不填读环境变量）" />
            </n-form-item>
            <n-form-item>
              <template #label>
                <span>发布时间过滤</span>
                <n-tooltip placement="right" trigger="hover" style="max-width:320px">
                  <template #trigger>
                    <n-icon class="ml-1 cursor-pointer" style="font-size:13px;color:#aaa;vertical-align:-2px">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
                    </n-icon>
                  </template>
                  <div style="font-size:12px;line-height:1.9">
                    <b>按文章/笔记发布时间过滤 DB 数据（推荐用于自动任务）</b><br/>
                    快捷预设在任务<b>每次执行时</b>动态计算起始日期，无需手动更新。<br/>
                    • 微信：对应 create_time_str 字段<br/>
                    • 小红书：对应 time 字段（Unix 秒）<br/>
                    选「不限」则上传全部历史数据
                  </div>
                </n-tooltip>
              </template>
              <n-select
                v-model:value="step.publish_date_range"
                :options="publishDateRangeOptions"
                style="width:200px"
              />
            </n-form-item>
            <!-- 自定义模式才显示手动日期选择器 -->
            <template v-if="step.publish_date_range === 'custom'">
              <n-form-item label="发布时间（起）">
                <n-date-picker
                  v-model:formatted-value="step.publish_date_start"
                  value-format="yyyy-MM-dd"
                  type="date"
                  clearable
                  placeholder="不限起始"
                  style="width:200px"
                />
              </n-form-item>
              <n-form-item label="发布时间（止）">
                <n-date-picker
                  v-model:formatted-value="step.publish_date_end"
                  value-format="yyyy-MM-dd"
                  type="date"
                  clearable
                  placeholder="不限截止"
                  style="width:200px"
                />
              </n-form-item>
            </template>
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
              <div style="width:100%">
                <n-select
                  :value="step.json_columns ? step.json_columns.split(',').map((c:string)=>c.trim()).filter(Boolean) : []"
                  @update:value="(v: string[]) => step.json_columns = v.join(',')"
                  multiple filterable tag
                  :options="(_jsonColsCache[step.table_id] || []).map((c:string) => ({label:c, value:c}))"
                  :loading="_jsonColsLoading[step.table_id]"
                  placeholder="在此输入 JSON 列名，回车确认（如 AI文本分析）"
                  style="width:100%"
                  @focus="loadJsonColumnsForStep(step.table_id)"
                />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">指本地数据集中内容为 JSON 字符串的列名，与目标飞书表列名无关</n-text>
              </div>
            </n-form-item>
            <n-form-item label="主键列">
              <n-input v-model:value="step.json_primary" placeholder="默认: 记录ID" />
            </n-form-item>
            <n-form-item label="未知字段">
              <div style="width:100%">
                <n-select
                  v-model:value="step.unknown_fields"
                  :options="[
                    {label:'skip — 静默跳过（推荐）', value:'skip'},
                    {label:'warn — 日志警告后跳过', value:'warn'},
                    {label:'error — 遇到未知字段报错', value:'error'},
                  ]"
                  placeholder="skip（默认）"
                />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">目标表二中不存在的字段（如正文内容）的处理方式；skip 不会在表二创建多余字段</n-text>
              </div>
            </n-form-item>
            <n-form-item label="封面索引字段">
              <div style="width:100%">
                <n-input v-model:value="step.cover_source_field" placeholder="留空自动识别 文章ID / article_id" />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">JSON记录中用于查找封面图片的文章ID字段名</n-text>
              </div>
            </n-form-item>
            <n-form-item label="封面目标字段">
              <div style="width:100%">
                <n-input v-model:value="step.wechat_cover_field" placeholder="image（留空时 wechat 平台自动用 image）" />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">封面图写入的飞书字段名；非空时自动启用封面上传，不填则 wechat 平台默认写入 image 字段</n-text>
              </div>
            </n-form-item>
            <n-form-item label="标题去重字段">
              <div style="width:100%">
                <n-select
                  v-if="_fieldCacheState[step.table_id]?.length"
                  v-model:value="step.json_dedup"
                  :options="_fieldCacheState[step.table_id]"
                  filterable
                  tag
                  clearable
                  placeholder="选择去重字段（留空不去重）"
                />
                <n-input v-else v-model:value="step.json_dedup" placeholder="按此字段去重（留空不去重，如 title）" />
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">同一字段值多次出现时只保留首条（经字段映射后的字段名）</n-text>
              </div>
            </n-form-item>
            <n-form-item label="字段映射">
              <div style="width:100%">
                <n-dynamic-input
                  v-model:value="step.field_mapping_rows"
                  :on-create="() => ({ src: '', dst: '' })"
                  #default="{ value: row }"
                >
                  <div style="display:flex;gap:8px;width:100%;align-items:center">
                    <n-input v-model:value="row.src" placeholder="原字段名（如 title）" style="flex:1" />
                    <n-text style="flex-shrink:0">→</n-text>
                    <n-select
                      v-if="_fieldCacheState[step.table_id]?.length"
                      v-model:value="row.dst"
                      :options="_fieldCacheState[step.table_id]"
                      filterable
                      tag
                      clearable
                      placeholder="目标字段名（可手输）"
                      style="flex:1"
                    />
                    <n-input
                      v-else
                      v-model:value="row.dst"
                      placeholder="目标字段名（如 活动名称）"
                      style="flex:1"
                    />
                  </div>
                </n-dynamic-input>
                <n-text depth="3" style="font-size:11px;width:100%;margin-top:2px;display:block">推送前重命名字段（源数据字段 → 目标飞书表字段），在字段过滤之前执行</n-text>
              </div>
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
                    placeholder="复选框: true/false  时间戳: now  文本/单选: 原始值"
                    style="flex:3;min-width:0"
                    size="small"
                  />
                  <n-button size="tiny" quaternary type="error" @click="step._kv_pairs.splice(pi, 1)">×</n-button>
                </div>
                <n-button dashed size="small" block style="margin-top:4px" @click="(step._kv_pairs = step._kv_pairs || []).push({ key: '', value: '' })">+ 添加字段</n-button>
                <n-text depth="3" style="font-size:11px;margin-top:2px;display:block">复选框字段填 true / false；时间戳填 now；文本/单选（含"是"/"否" 选项）直接填写原始值</n-text>
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

      <!-- M-1降级版：步骤间连通性指示 -->
      <div v-if="idx < pipelineSteps.length - 1" class="step-connector">
        <template v-if="getStepOutput(idx) && getStepInput(idx + 1)">
          <div :class="['step-connector-line', getStepOutput(idx) === getStepInput(idx + 1) ? 'connected' : 'mismatch']">
            <span class="connector-arrow">↓</span>
            <n-tag
              size="tiny"
              :type="getStepOutput(idx) === getStepInput(idx + 1) ? 'success' : 'error'"
              style="font-size:11px"
            >
              <template v-if="getStepOutput(idx) === getStepInput(idx + 1)">
                ✓ {{ getStepOutput(idx) }}
              </template>
              <template v-else>
                ⚠ {{ getStepOutput(idx) }} ≠ {{ getStepInput(idx + 1) }}
              </template>
            </n-tag>
          </div>
        </template>
        <template v-else>
          <div class="step-connector-line neutral">
            <span class="connector-arrow">↓</span>
          </div>
        </template>
      </div>
      </template>

      <n-button dashed block size="small" @click="addStep">+ 添加步骤</n-button>

      <template #action>
        <n-space style="width:100%;justify-content:space-between">
          <n-space>
            <n-button size="small" @click="openTemplateModal">从模板加载</n-button>
            <n-button size="small" @click="saveAsTemplate">另存为模板</n-button>
          </n-space>
          <n-space>
            <n-button @click="cancelCreate()">取消</n-button>
            <n-button type="primary" @click="editingTaskId ? updateTask() : createTask()">{{ editingTaskId ? '保存' : '创建' }}</n-button>
          </n-space>
        </n-space>
      </template>
    </n-modal>

    <!-- Template Picker Modal -->
    <n-modal v-model:show="showTemplateModal" title="选择任务模板" preset="dialog" style="width: 680px">
      <n-spin :show="templateLoading">
        <n-empty v-if="!templates.length && !templateLoading" description="暂无模板，可在编辑任务时选择「另存为模板」来保存" />
        <n-list bordered v-if="templates.length">
          <n-list-item v-for="t in templates" :key="t.id">
            <n-space align="center" justify="space-between">
              <div>
                <div style="font-weight:500">{{ t.name }}</div>
                <div class="text-xs text-gray-400" v-if="t.description">{{ t.description }}</div>
                <n-space :size="4" style="margin-top:4px" v-if="t.tags?.length">
                  <n-tag v-for="tag in t.tags" :key="tag" size="tiny">{{ tag }}</n-tag>
                </n-space>
              </div>
              <n-space>
                <n-button size="small" type="primary" @click="applyTemplate(t.id)">加载</n-button>
                <n-button size="small" type="error" quaternary :disabled="t.is_builtin" @click="deleteTemplate(t.id)">删除</n-button>
              </n-space>
            </n-space>
          </n-list-item>
        </n-list>
      </n-spin>
      <template #action>
        <n-button @click="showTemplateModal = false">关闭</n-button>
      </template>
    </n-modal>
    <!-- Save Template Modal -->
    <n-modal v-model:show="showSaveTemplateModal" title="另存为模板" preset="dialog" style="width: 420px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="模板名称">
          <n-input v-model:value="saveTemplateName" placeholder="请输入模板名称" @keyup.enter="confirmSaveTemplate" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showSaveTemplateModal = false">取消</n-button>
        <n-button type="primary" @click="confirmSaveTemplate">保存</n-button>
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
const execLogMeta = ref<{ execution_id?: number; status?: string; trigger_type?: string; started_at?: string; finished_at?: string; duration_seconds?: number; pipeline_steps?: any[]; dry_run_report?: string[]; is_dry_run?: boolean }>({  })
const logRef = ref<any>(null)
const _isPolling = ref(false)
let _logPollTimer: ReturnType<typeof setInterval> | null = null

// ─── 任务模板 ─────────────────────────────────────────────────────────────────
const showTemplateModal = ref(false)
const templates = ref<any[]>([])
const templateLoading = ref(false)
const showSaveTemplateModal = ref(false)
const saveTemplateName = ref('')
const saveTemplateConfig = ref<any>(null)

async function loadTemplates() {
  templateLoading.value = true
  try {
    const res = await http.get('/scheduler/templates')
    templates.value = unwrapApiData(res.data) || []
  } catch {
    templates.value = []
  } finally {
    templateLoading.value = false
  }
}

async function openTemplateModal() {
  showTemplateModal.value = true
  await loadTemplates()
}

async function applyTemplate(templateId: number) {
  try {
    const res = await http.post(`/scheduler/templates/${templateId}/apply`)
    const data = unwrapApiData(res.data) as any
    // 预填任务配置
    newTask.value.task_type = data.task_type || newTask.value.task_type
    if (data.platform) newTask.value.platform = data.platform
    restorePipelineFromConfig(data.task_config, data.task_type, data.platform || newTask.value.platform)
    showTemplateModal.value = false
    message.success('模板已加载，请确认配置后保存')
  } catch (e: any) {
    message.error(`加载模板失败: ${e?.message ?? '未知错误'}`)
  }
}

async function saveAsTemplate() {
  // 先序列化当前 pipeline 配置
  let taskConfig: any
  try {
    taskConfig = buildTaskConfig()
  } catch (e: any) {
    message.error(`序列化配置失败: ${e?.message}`)
    return
  }
  const rawName = newTask.value.name || '未命名任务'
  const suggestedName = rawName + ' 模板'
  showSaveTemplateModal.value = true
  saveTemplateName.value = suggestedName
  saveTemplateConfig.value = taskConfig
}

async function confirmSaveTemplate() {
  const name = saveTemplateName.value.trim()
  if (!name) { message.warning('请输入模板名称'); return }
  try {
    await http.post('/scheduler/templates', {
      name,
      task_type: newTask.value.task_type || 'pipeline',
      platform: newTask.value.platform || null,
      task_config: saveTemplateConfig.value,
      tags: newTask.value.platform ? [newTask.value.platform] : [],
    })
    message.success('模板已保存')
    showSaveTemplateModal.value = false
  } catch (e: any) {
    message.error(`保存失败: ${e?.message}`)
  }
}

async function deleteTemplate(templateId: number) {
  try {
    await http.delete(`/scheduler/templates/${templateId}`)
    message.success('模板已删除')
    await loadTemplates()
  } catch (e: any) {
    message.error(`删除失败: ${e?.message}`)
  }
}

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
    if (['feishu_pull', 'feishu_update_records', 'feishu_push_json'].includes(step.step)) {
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
const schedulePreset = ref<'daily' | 'weekly' | 'hourly' | 'custom' | 'once'>('hourly')
const dailyTime = ref({ hour: 8, minute: 0 })
const weeklyDays = ref<number[]>([1])
const weeklyTime = ref({ hour: 8, minute: 0 })
const onceRunAt = ref('')
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
  { label: '文章 — 微信公众号采集内容', value: 'article' },
  { label: '笔记/视频 — 小红书·抖音·B站·微博等', value: 'note' },
  { label: '创作者 — 账号/用户元信息', value: 'creator' },
]

const dateRangeOptions = [
  { label: '不限制（全部内容）', value: 'all' },
  { label: '过去 1 天', value: 'past_1d' },
  { label: '过去 3 天', value: 'past_3d' },
  { label: '过去 7 天（约1周）', value: 'past_7d' },
  { label: '过去 30 天（约1月）', value: 'past_30d' },
  { label: '自定义日期范围', value: 'custom' },
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
const publishDateRangeOptions = [
  { label: '不限（上传全部）', value: 'all' },
  { label: '过去 7 天', value: '7d' },
  { label: '过去 15 天', value: '15d' },
  { label: '过去 1 个月', value: '30d' },
  { label: '过去 3 个月', value: '90d' },
  { label: '自定义', value: 'custom' },
]
/** M-6: json_columns 动态列名缓存 */
const _jsonColsCache = ref<Record<string, string[]>>({})
const _jsonColsLoading = ref<Record<string, boolean>>({})

async function loadJsonColumnsForStep(tableId: string) {
  if (!tableId || _jsonColsCache.value[tableId] !== undefined) return
  _jsonColsLoading.value[tableId] = true
  try {
    const { data } = await http.get('/scheduler/datasets/columns', { params: { table_id: tableId } })
    const cols = data?.data?.columns || []
    _jsonColsCache.value = { ..._jsonColsCache.value, [tableId]: cols }
  } catch {
    _jsonColsCache.value = { ..._jsonColsCache.value, [tableId]: [] }
  } finally {
    _jsonColsLoading.value[tableId] = false
    _jsonColsLoading.value = { ..._jsonColsLoading.value }
  }
}

/** M-1降级版：获取 idx 步骤的输出变量名（仅 feishu_pull） */
function getStepOutput(idx: number): string {
  const s = pipelineSteps.value[idx]
  if (!s) return ''
  if (s.step === 'feishu_pull') return s.output || ''
  return ''
}

/** M-1降级版：获取 idx 步骤所需的输入变量名（feishu_push_json / feishu_update_records） */
function getStepInput(idx: number): string {
  const s = pipelineSteps.value[idx]
  if (!s) return ''
  if (['feishu_push_json', 'feishu_update_records'].includes(s.step)) return s.input || ''
  return ''
}

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

const schedulePresetOptions = [
  { label: '每天（固定时间）', value: 'daily' },
  { label: '每周（指定星期）', value: 'weekly' },
  { label: '每隔 N 小时', value: 'hourly' },
  { label: '自定义 Cron', value: 'custom' },
  { label: '执行一次', value: 'once' },
]

const weekdayOptions = [
  { label: '周日', value: 0 }, { label: '周一', value: 1 },
  { label: '周二', value: 2 }, { label: '周三', value: 3 },
  { label: '周四', value: 4 }, { label: '周五', value: 5 },
  { label: '周六', value: 6 },
]

const hourOptions = Array.from({ length: 24 }, (_, i) => ({ label: `${i} 时`, value: i }))
const minuteOptions = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map(m => ({ label: `${m} 分`, value: m }))

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
      return { step: 'subscription_crawl', platform: p, limit: 0, timeout_seconds: p === 'xhs' || p === 'dy' ? 2700 : 3600, only_creator_ids: [], date_range_type: 'all', date_range_start: '', date_range_end: '' }
    case 'crawl':
      return {
        step: 'crawl', platform: p,
        crawler_type: 'search', keywords: '', creator_ids: '',
        limit: 0,
        timeout_seconds: p === 'xhs' || p === 'dy' ? 2700 : 1800,
        retry_count: needRetry ? 2 : 0,
        retry_delay: 30,
        date_range_type: 'all', date_range_start: '', date_range_end: '',
      }
    case 'feishu_push':
      return { step: 'feishu_push', platform: p, data_type: dataType, table_id: '', publish_date_range: 'all', publish_date_start: null, publish_date_end: null }
    case 'feishu_pull':
      return { step: 'feishu_pull', platform: p, table_id: '', filter_field: '', filter_operator: 'contains', filter_values: [], view_id: '', filter_conjunction: 'and', output_format: 'sqlite', output: 'feishu_pull_result' }
    case 'feishu_push_json':
      return { step: 'feishu_push_json', input: 'feishu_pull_result', table_id: '', json_columns: '', json_primary: '记录ID', unknown_fields: 'skip', cover_source_field: '', wechat_cover_field: '', field_mapping_rows: [], range_start: null, range_end: null, json_dedup: '' }
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
  schedulePreset.value = 'hourly'
  intervalHours.value = 6
  cronExpr.value = ''
  dailyTime.value = { hour: 8, minute: 0 }
  weeklyDays.value = [1]
  weeklyTime.value = { hour: 8, minute: 0 }
  onceRunAt.value = ''
  pipelineSteps.value = getDefaultPipeline('subscription_combo', 'wechat')
}

/** 将当前 schedulePreset + 相关 ref 转换为后端需要的 schedule_type + schedule_config */
function buildScheduleConfig(): { schedule_type: string; schedule_config: any } {
  switch (schedulePreset.value) {
    case 'daily': {
      const m = String(dailyTime.value.minute).padStart(2, '0')
      const h = String(dailyTime.value.hour)
      return { schedule_type: 'cron', schedule_config: { cron: `${m} ${h} * * *` } }
    }
    case 'weekly': {
      if (!weeklyDays.value.length) throw new Error('请至少选择一个星期')
      const m = String(weeklyTime.value.minute).padStart(2, '0')
      const h = String(weeklyTime.value.hour)
      const dow = weeklyDays.value.join(',')
      return { schedule_type: 'cron', schedule_config: { cron: `${m} ${h} * * ${dow}` } }
    }
    case 'hourly':
      return { schedule_type: 'interval', schedule_config: { hours: intervalHours.value } }
    case 'custom': {
      if (!cronExpr.value.trim()) throw new Error('请填写 Cron 表达式')
      return { schedule_type: 'cron', schedule_config: { cron: cronExpr.value.trim() } }
    }
    case 'once':
      if (!onceRunAt.value.trim()) throw new Error('请填写执行时间')
      return { schedule_type: 'once', schedule_config: { run_at: onceRunAt.value.trim() } }
    default:
      return { schedule_type: 'interval', schedule_config: { hours: 6 } }
  }
}

/** 从已保存的 task 恢复调度方式 UI 状态 */
function restoreScheduleFromTask(task: any) {
  const st: string = task.schedule_type || 'interval'
  const sc: any = task.schedule_config || {}
  if (st === 'interval') {
    schedulePreset.value = 'hourly'
    intervalHours.value = sc.hours || 6
  } else if (st === 'cron') {
    const expr: string = sc.cron || ''
    const parts = expr.split(' ')
    if (parts.length === 5 && parts[2] === '*' && parts[3] === '*' && parts[4] === '*') {
      // 每天
      schedulePreset.value = 'daily'
      dailyTime.value = { hour: parseInt(parts[1]) || 8, minute: parseInt(parts[0]) || 0 }
    } else if (parts.length === 5 && parts[2] === '*' && parts[3] === '*' && parts[4] !== '*') {
      // 每周
      schedulePreset.value = 'weekly'
      weeklyTime.value = { hour: parseInt(parts[1]) || 8, minute: parseInt(parts[0]) || 0 }
      weeklyDays.value = parts[4].split(',').map(Number).filter((n: number) => !isNaN(n))
    } else {
      schedulePreset.value = 'custom'
      cronExpr.value = expr
    }
  } else if (st === 'once') {
    schedulePreset.value = 'once'
    onceRunAt.value = sc.run_at || ''
  } else {
    schedulePreset.value = 'hourly'
    intervalHours.value = 6
  }
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
      if (s.date_range_type && s.date_range_type !== 'all') {
        clean.date_range_type = s.date_range_type
        if (s.date_range_type === 'custom') {
          if (s.date_range_start) clean.date_range_start = s.date_range_start
          if (s.date_range_end) clean.date_range_end = s.date_range_end
        }
      }
    }
    if (s.step === 'crawl') {
      clean.crawler_type = s.crawler_type || 'search'
      if (s.keywords) clean.keywords = s.keywords
      if (s.creator_ids) clean.creator_ids = s.creator_ids
      if (s.limit && Number(s.limit) > 0) clean.limit = Number(s.limit)
      if (s.timeout_seconds && s.timeout_seconds !== 1800) clean.timeout_seconds = s.timeout_seconds
      if (s.retry_count && Number(s.retry_count) > 0) clean.retry_count = Number(s.retry_count)
      if (s.retry_delay && Number(s.retry_delay) !== 30) clean.retry_delay = Number(s.retry_delay)
      if (s.date_range_type && s.date_range_type !== 'all') {
        clean.date_range_type = s.date_range_type
        if (s.date_range_type === 'custom') {
          if (s.date_range_start) clean.date_range_start = s.date_range_start
          if (s.date_range_end) clean.date_range_end = s.date_range_end
        }
      }
    }
    if (s.step === 'feishu_push') {
      if (s.data_type) clean.data_type = s.data_type
      if (s.table_id) clean.table_id = s.table_id
      if (s.publish_date_range && s.publish_date_range !== 'all') {
        clean.publish_date_range = s.publish_date_range
        if (s.publish_date_range === 'custom') {
          if (s.publish_date_start) clean.publish_date_start = s.publish_date_start
          if (s.publish_date_end) clean.publish_date_end = s.publish_date_end
        }
      }
    }
    if (s.step === 'feishu_pull') {
      if (s.table_id) clean.table_id = s.table_id
      if (s.filter_field && s.filter_values?.length) {
        clean.filter_field = s.filter_field
        clean.filter_operator = s.filter_operator
        clean.filter_values = s.filter_values
        if (s.filter_conjunction && s.filter_conjunction !== 'and') clean.filter_conjunction = s.filter_conjunction
      }
      if (s.view_id) clean.view_id = s.view_id
      if (s.output_format && s.output_format !== 'sqlite') clean.output_format = s.output_format
      if (s.output) clean.output = s.output
    }
    if (s.step === 'feishu_push_json') {
      if (s.input) clean.input = s.input
      if (s.table_id) clean.table_id = s.table_id
      if (s.json_columns) clean.json_columns = s.json_columns
      if (s.json_primary) clean.json_primary = s.json_primary
      if (s.unknown_fields && s.unknown_fields !== 'skip') clean.unknown_fields = s.unknown_fields
      if (s.cover_source_field) clean.cover_source_field = s.cover_source_field
      if (s.wechat_cover_field) clean.wechat_cover_field = s.wechat_cover_field
      if (s.json_dedup) clean.json_dedup = s.json_dedup
      // field_mapping_rows [{src, dst}] → field_mapping {src: dst}
      if (Array.isArray(s.field_mapping_rows) && s.field_mapping_rows.length) {
        const mapping: Record<string, string> = {}
        for (const row of s.field_mapping_rows) {
          if (row.src && row.dst && row.src !== row.dst) mapping[row.src] = row.dst
        }
        if (Object.keys(mapping).length) clean.field_mapping = mapping
      }
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
        // 仅将显式的英文 true/false 转为 boolean；
        // 中文"是"/"否" 原样保留为字符串，后端 _coerce_value_by_type 对复选框字段会自动识别。
        // 这样单选字段（选项为"是"/"否"）填写的值也能正确写入。
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
      // feishu_push_json: field_mapping {src: dst} → field_mapping_rows [{src, dst}]
      if (s.step === 'feishu_push_json' && s.field_mapping && typeof s.field_mapping === 'object') {
        merged.field_mapping_rows = Object.entries(s.field_mapping).map(([src, dst]) => ({ src, dst: String(dst) }))
        delete merged.field_mapping
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
        const expr: string = row.schedule_config?.cron || ''
        const parts = expr.split(' ')
        if (parts.length === 5 && parts[2] === '*' && parts[3] === '*' && parts[4] === '*') {
          const h = parts[1].padStart(2, '0')
          const m = parts[0].padStart(2, '0')
          return `每天 ${h}:${m}`
        }
        if (parts.length === 5 && parts[2] === '*' && parts[3] === '*' && parts[4] !== '*') {
          const h = parts[1].padStart(2, '0')
          const m = parts[0].padStart(2, '0')
          const dow = parts[4]
          const dayNames: Record<string, string> = { '0': '日', '1': '一', '2': '二', '3': '三', '4': '四', '5': '五', '6': '六' }
          const days = dow.split(',').map((d: string) => dayNames[d] ?? d).join('/')
          return `每周${days} ${h}:${m}`
        }
        return expr || 'cron'
      }
      if (row.schedule_type === 'once') {
        return `单次 ${row.schedule_config?.run_at?.slice(0, 16) ?? ''}`
      }
      return row.schedule_type
    },
  },
  {
    title: '操作', key: 'actions', width: 340,
    render: (row: any) =>
      h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => triggerTask(row) }, () => '执行'),
        h(NButton, { size: 'tiny', type: 'warning', onClick: () => dryRunTask(row) }, () => '试运行'),
        h(NButton, { size: 'tiny', type: 'info', onClick: () => openEdit(row) }, () => '编辑'),
        h(NButton, { size: 'tiny', onClick: () => toggleTask(row) }, () => row.is_active ? '禁用' : '启用'),
        h(NButton, { size: 'tiny', type: 'error', onClick: () => deleteTask(row.id) }, () => '删除'),
      ]),
  },
]

const execColumns: DataTableColumn[] = [
  { title: '任务', key: 'task_name', width: 160 },
  {
    title: '触发', key: 'trigger_type', width: 70,
    render: (row: any) => h(NTag, { size: 'small', type: row.trigger_type === 'dry_run' ? 'warning' : 'default' as any }, () =>
      row.trigger_type === 'manual' ? '手动' : row.trigger_type === 'dry_run' ? '试运行' : '定时'),
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
      trigger_type: payload.trigger_type,
      started_at: payload.started_at,
      finished_at: payload.finished_at,
      duration_seconds: payload.duration_seconds,
      pipeline_steps: payload.pipeline_steps || [],
      dry_run_report: payload.dry_run_report || [],
      is_dry_run: payload.trigger_type === 'dry_run',
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

async function cleanupExecutions() {
  dialog.warning({
    title: '清理执行记录',
    content: '将删除 7 天前已完成/失败/取消的执行记录。确认继续？',
    positiveText: '确认清理',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const { data } = await http.delete('/scheduler/executions', { params: { before_days: 7 } })
        const payload = unwrapApiData<any>(data) || {}
        message.success(`已清理 ${payload.deleted ?? 0} 条记录`)
        loadExecutions()
      } catch (e: any) {
        message.error(e.message || '清理失败')
      }
    },
  })
}

async function createTask() {
  if (!newTask.value.name.trim()) { message.warning('请填写任务名称'); return }
  let scheduleResult: { schedule_type: string; schedule_config: any }
  try { scheduleResult = buildScheduleConfig() } catch (e: any) { message.warning(e.message || '请完善调度配置'); return }
  try {
    let taskConfig: any
    try { taskConfig = buildTaskConfig() } catch (e: any) { message.error(e.message || '配置错误'); return }

    await http.post('/scheduler/tasks', {
      ...newTask.value,
      schedule_type: scheduleResult.schedule_type,
      schedule_config: scheduleResult.schedule_config,
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
  restoreScheduleFromTask(row)

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
  let scheduleResult: { schedule_type: string; schedule_config: any }
  try { scheduleResult = buildScheduleConfig() } catch (e: any) { message.warning(e.message || '请完善调度配置'); return }
  try {
    let taskConfig: any
    try { taskConfig = buildTaskConfig() } catch (e: any) { message.error(e.message || '配置错误'); return }

    // P0-1 FIX: 发送完整字段（包含 task_type / platform / task_config）
    await http.put(`/scheduler/tasks/${editingTaskId.value}`, {
      name: newTask.value.name,
      task_type: newTask.value.task_type,
      platform: newTask.value.platform,
      schedule_type: scheduleResult.schedule_type,
      schedule_config: scheduleResult.schedule_config,
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

async function dryRunTask(row: any) {
  try {
    const { data } = await http.post(`/scheduler/tasks/${row.id}/dry-run`)
    message.info(data.message || '试运行已触发')
    loadExecutions()
    const execId = data?.data?.execution_id
    if (execId) openExecutionLog(execId)
  } catch (e: any) {
    message.error(e.message || '试运行触发失败')
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

<style scoped>
/* M-1 降级版：步骤间连通性指示 */
.step-connector {
  display: flex;
  align-items: center;
  padding: 0 0 0 18px;
  margin: 2px 0;
  min-height: 28px;
}
.step-connector-line {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}
.connector-arrow {
  font-size: 15px;
  line-height: 1;
  color: #c0c4cc;
  transition: color 0.2s;
}
.step-connector-line.connected .connector-arrow { color: #18a058; }
.step-connector-line.mismatch  .connector-arrow { color: #d03050; }
.step-connector-line.neutral   .connector-arrow { color: #c0c4cc; }
</style>
