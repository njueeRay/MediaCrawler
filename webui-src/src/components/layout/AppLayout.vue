<template>
  <n-layout has-sider style="height: 100vh">
    <!-- Sidebar -->
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :collapsed="appStore.sidebarCollapsed"
      show-trigger
      @collapse="appStore.sidebarCollapsed = true"
      @expand="appStore.sidebarCollapsed = false"
      :native-scrollbar="false"
    >
      <div class="flex items-center justify-center h-14 border-b border-gray-200 dark:border-gray-700">
        <span v-if="!appStore.sidebarCollapsed" class="text-lg font-bold">MediaCrawler</span>
        <span v-else class="text-lg font-bold">MC</span>
      </div>
      <n-menu
        :collapsed="appStore.sidebarCollapsed"
        :collapsed-width="64"
        :collapsed-icon-size="22"
        :options="menuOptions"
        :value="currentRoute"
        @update:value="handleMenuClick"
      />
    </n-layout-sider>

    <!-- Main content -->
    <n-layout>
      <n-layout-header bordered class="flex items-center justify-between h-14 px-6">
        <div class="text-base font-medium">{{ currentTitle }}</div>
        <div class="flex items-center gap-3">
          <n-switch :value="appStore.darkMode" @update:value="appStore.toggleDarkMode">
            <template #checked>🌙</template>
            <template #unchecked>☀️</template>
          </n-switch>
        </div>
      </n-layout-header>
      <n-layout-content content-style="padding: 24px;" :native-scrollbar="false">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NIcon } from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import {
  HomeOutline,
  SettingsOutline,
  PeopleOutline,
  GridOutline,
  SwapHorizontalOutline,
  CloudUploadOutline,
  TimerOutline,
  TerminalOutline,
} from '@vicons/ionicons5'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const route = useRoute()
const router = useRouter()

const currentRoute = computed(() => route.name as string)
const currentTitle = computed(() => {
  const matched = route.matched.find(r => r.meta?.title)
  return (matched?.meta?.title as string) || 'MediaCrawler WebUI'
})

function renderIcon(icon: any) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions: MenuOption[] = [
  { label: '仪表盘', key: 'Dashboard', icon: renderIcon(HomeOutline) },
  { label: '配置管理', key: 'ConfigManager', icon: renderIcon(SettingsOutline) },
  { label: '订阅管理', key: 'Subscription', icon: renderIcon(PeopleOutline) },
  { label: '数据浏览', key: 'DataExplorer', icon: renderIcon(GridOutline) },
  { label: '字段映射', key: 'FieldMapping', icon: renderIcon(SwapHorizontalOutline) },
  { label: '飞书同步', key: 'FeishuSync', icon: renderIcon(CloudUploadOutline) },
  { label: '任务调度', key: 'TaskScheduler', icon: renderIcon(TimerOutline) },
  { label: '日志监控', key: 'Logs', icon: renderIcon(TerminalOutline) },
]

function handleMenuClick(key: string) {
  router.push({ name: key })
}
</script>
