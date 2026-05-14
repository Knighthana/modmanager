<template>
  <div class="database-selector" style="display: flex; align-items: center; gap: 8px;">
    <el-select v-model="selectedDatabase" placeholder="选择 database" style="width: 220px;">
      <el-option v-for="opt in options" :key="opt.value" :label="opt.label" :value="opt.value" />
    </el-select>
    <el-tag v-if="hasDecisions" size="small" type="warning" effect="plain">有历史决策</el-tag>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { apiPost } from '../api/client'
import { loadWorkspace, saveWorkspace } from '../utils/persistence'

interface DatabaseOption {
  label: string
  value: string
}

const options = ref<DatabaseOption[]>([])
const selectedDatabase = ref('default')
const hasDecisions = ref(false)

onMounted(async () => {
  try {
    const resp = await apiPost<Record<string, unknown>>('/config/discover', {})
    if (resp.ok && resp.data) {
      const databases = (resp.data as Record<string, unknown>).databases as Record<string, unknown> | undefined
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

  // 读上次选中的 database
  const ws = loadWorkspace()
  if (ws.lastDatabase && options.value.some(o => o.value === ws.lastDatabase)) {
    selectedDatabase.value = ws.lastDatabase
  }

  // 检查当前选中是否有历史决策
  checkDecisions()
})

function checkDecisions() {
  const ws = loadWorkspace()
  const perDb = ws.perDatabase?.[selectedDatabase.value]
  hasDecisions.value = !!(perDb?.decisions && Object.keys(perDb.decisions).length > 0)
}

watch(selectedDatabase, () => {
  checkDecisions()
})

defineExpose({ selectedDatabase, options })
</script>
