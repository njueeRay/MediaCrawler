<template>
  <n-alert title="需要数据库" type="warning" class="mb-4" closable>
    当前存储模式为 CSV/JSON，此页面的功能需要数据库支持。
    请前往
    <n-button text type="primary" size="small" @click="router.push({ name: 'ConfigManager' })">配置管理</n-button>
    页面，将存储模式切换到 DB (SQLite / MySQL / PostgreSQL)，然后重启服务。
  </n-alert>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
