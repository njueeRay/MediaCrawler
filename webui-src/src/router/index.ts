import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/dashboard',
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

export default router
