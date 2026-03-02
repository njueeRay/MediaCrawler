import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // ── 公开路由（无需鉴权）──────────────────────────────────────────────────
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { title: '登录', public: true },
    },

    // ── 受保护路由（需要登录）────────────────────────────────────────────────
    {
      path: '/',
      component: AppLayout,
      redirect: '/dashboard',
      meta: { requiresAuth: true },
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '仪表盘', icon: 'HomeOutline' },
        },
        {
          path: 'config',
          name: 'ConfigManager',
          component: () => import('@/views/ConfigManager.vue'),
          meta: { title: '配置管理', icon: 'SettingsOutline' },
        },
        {
          path: 'subscription',
          name: 'Subscription',
          component: () => import('@/views/Subscription.vue'),
          meta: { title: '订阅管理', icon: 'PeopleOutline' },
        },
        {
          path: 'data',
          name: 'DataExplorer',
          component: () => import('@/views/DataExplorer.vue'),
          meta: { title: '数据浏览', icon: 'GridOutline' },
        },
        {
          path: 'mapping',
          name: 'FieldMapping',
          component: () => import('@/views/FieldMapping.vue'),
          meta: { title: '字段映射', icon: 'SwapHorizontalOutline' },
        },
        {
          path: 'feishu',
          name: 'FeishuSync',
          component: () => import('@/views/FeishuSync.vue'),
          meta: { title: '飞书同步', icon: 'CloudUploadOutline' },
        },
        {
          path: 'scheduler',
          name: 'TaskScheduler',
          component: () => import('@/views/TaskScheduler.vue'),
          meta: { title: '任务调度', icon: 'TimerOutline' },
        },
        {
          path: 'logs',
          name: 'Logs',
          component: () => import('@/views/Logs.vue'),
          meta: { title: '日志监控', icon: 'TerminalOutline' },
        },
      ],
    },
  ],
})

// ── 全局导航守卫（W-01）──────────────────────────────────────────────────────
router.beforeEach((to) => {
  const token = localStorage.getItem('mc_access_token')
  const isAuthenticated = !!token

  // 访问登录页：已登录 → 跳转 dashboard
  if (to.name === 'Login' && isAuthenticated) {
    return { name: 'Dashboard' }
  }

  // 访问受保护页：未登录 → 跳转登录（携带来源路径）
  const requiresAuth = to.matched.some((r) => r.meta?.requiresAuth)
  if (requiresAuth && !isAuthenticated) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  return true
})

export default router
