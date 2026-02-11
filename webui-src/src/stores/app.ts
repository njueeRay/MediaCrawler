import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useAppStore = defineStore('app', () => {
  const darkMode = ref(localStorage.getItem('mc-dark-mode') === 'true')
  const sidebarCollapsed = ref(localStorage.getItem('mc-sidebar-collapsed') === 'true')
  const dbConfigured = ref(true) // tracks whether backend has DB

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  // Persist preferences
  watch(darkMode, (v) => localStorage.setItem('mc-dark-mode', String(v)))
  watch(sidebarCollapsed, (v) => localStorage.setItem('mc-sidebar-collapsed', String(v)))

  return { darkMode, sidebarCollapsed, dbConfigured, toggleDarkMode, toggleSidebar }
})
