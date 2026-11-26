import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getHealth } from '../api/health'
import type { HealthStatus } from '../types/api'

export const useSystemStore = defineStore('system', () => {
  const health = ref<HealthStatus | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function refresh(checkDatabase = false) {
    loading.value = true
    error.value = ''
    health.value = null
    try {
      health.value = await getHealth(checkDatabase)
    } catch {
      error.value = checkDatabase
        ? '连接检查失败，请确认后端已启动，并检查 MySQL 配置。'
        : '暂时无法连接后端，请确认服务已在 8000 端口启动。'
    } finally {
      loading.value = false
    }
  }
  return { health, loading, error, refresh }
})
