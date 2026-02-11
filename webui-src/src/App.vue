<template>
  <n-config-provider :theme="appStore.darkMode ? darkTheme : undefined" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <router-view />
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { darkTheme, zhCN, dateZhCN } from 'naive-ui'
import { useAppStore } from '@/stores/app'
import { watchEffect } from 'vue'

const appStore = useAppStore()

// Sync dark mode to document element for TailwindCSS dark: utilities
watchEffect(() => {
  document.documentElement.classList.toggle('dark', appStore.darkMode)
})
</script>
