<template>
  <div class="login-bg">
    <n-card class="login-card" :bordered="true">
      <!-- Logo / 标题 -->
      <div class="login-header">
        <div class="login-logo">🕷️</div>
        <div class="login-title">MediaCrawler</div>
        <div class="login-subtitle">WebUI 管理后台</div>
      </div>

      <!-- 登录表单 -->
      <n-form
        ref="formRef"
        :model="form"
        :rules="rules"
        size="large"
        @keydown.enter.prevent="handleLogin"
      >
        <n-form-item path="username" label="用户名">
          <n-input
            v-model:value="form.username"
            placeholder="请输入用户名"
            :disabled="authStore.loading"
            autocomplete="username"
          >
            <template #prefix>
              <n-icon :component="PersonOutline" />
            </template>
          </n-input>
        </n-form-item>

        <n-form-item path="password" label="密码">
          <n-input
            v-model:value="form.password"
            type="password"
            placeholder="请输入密码"
            show-password-on="click"
            :disabled="authStore.loading"
            autocomplete="current-password"
          >
            <template #prefix>
              <n-icon :component="LockClosedOutline" />
            </template>
          </n-input>
        </n-form-item>

        <!-- 错误提示 -->
        <n-alert
          v-if="authStore.error"
          type="error"
          :show-icon="true"
          closable
          @close="authStore.error = null"
          class="mb-4"
        >
          {{ authStore.error }}
        </n-alert>

        <n-button
          type="primary"
          block
          :loading="authStore.loading"
          @click="handleLogin"
          class="mt-2"
        >
          登录
        </n-button>
      </n-form>

      <n-divider />
      <p class="login-tip">默认账号 <code>admin</code>，密码在 <code>ADMIN_PASSWORD</code> 环境变量中配置</p>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { FormInst, FormRules } from 'naive-ui'
import { NIcon } from 'naive-ui'
import { PersonOutline, LockClosedOutline } from '@vicons/ionicons5'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const formRef = ref<FormInst | null>(null)

const form = ref({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  try {
    await authStore.login(form.value.username, form.value.password)
    // 登录成功 → 跳回来源页或默认 dashboard
    const redirect = (route.query.redirect as string) || '/dashboard'
    await router.replace(redirect)
  } catch {
    // authStore.error 已被 store 设置，直接展示
  }
}
</script>

<style scoped>
.login-bg {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-card {
  width: 400px;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.login-header {
  text-align: center;
  margin-bottom: 24px;
}

.login-logo {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 8px;
}

.login-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--n-text-color);
}

.login-subtitle {
  font-size: 13px;
  color: var(--n-text-color-3);
  margin-top: 4px;
}

.login-tip {
  font-size: 12px;
  color: var(--n-text-color-3);
  text-align: center;
  margin: 0;
}

.login-tip code {
  background: var(--n-code-color);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}

.mb-4 {
  margin-bottom: 16px;
}

.mt-2 {
  margin-top: 8px;
}
</style>
