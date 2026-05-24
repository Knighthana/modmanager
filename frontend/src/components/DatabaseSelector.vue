<template>
  <div class="database-selector" style="display: flex; align-items: center; gap: 8px;">
    <el-select v-model="selectedDatabase" placeholder="选择 database" style="width: 220px;">
      <el-option v-for="opt in options" :key="opt.value" :label="opt.label" :value="opt.value" />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiPost } from '../api/transport'

interface DatabaseOption {
  label: string
  value: string
}

const options = ref<DatabaseOption[]>([])
const selectedDatabase = ref('default')

onMounted(async () => {
  try {
    const resp = await apiPost<Record<string, unknown>>('/config/discover', {})
    if (resp.ok && resp.data) {
      const data = resp.data as Record<string, unknown>
      const config = data.config as Record<string, unknown> | undefined
      const databases = config?.databases as Record<string, unknown> | undefined
      if (databases && typeof databases === 'object') {
        const keys = Object.keys(databases)
        if (keys.length > 0) {
          options.value = keys.map(k => ({ label: k, value: k }))
        }
      }
    }
  } catch {
    // 接口不可用时使用默认值
  }
})

defineExpose({ selectedDatabase, options })
</script>
