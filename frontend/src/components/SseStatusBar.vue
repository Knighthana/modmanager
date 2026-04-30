<template>
  <el-footer style="padding: 8px 16px; border-top: 1px solid var(--el-border-color-light); background: var(--el-bg-color);">
    <div style="display: flex; align-items: center; gap: 12px;">
      <el-progress
        :percentage="percentage"
        :stroke-width="16"
        :text-inside="false"
        style="flex: 1;"
      />
      <span style="font-size: 13px; color: var(--el-text-color-secondary); white-space: nowrap;">
        {{ store.progress.step }}: {{ store.progress.message }}
      </span>
    </div>
  </el-footer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useForestStore } from '../stores/forest'

const store = useForestStore()

const percentage = computed(() => {
  const { finished, total } = store.progress
  if (total <= 0) return 0
  return Math.round((finished / total) * 100)
})
</script>
